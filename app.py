"""Cloud Run entrypoint. One endpoint, /post, invoked by Cloud Scheduler (or
manually for testing). Orchestrates: pick topic -> generate + validate
(retrying) -> source image -> post -> record state.

Logs a POST_SKIPPED error line when a day is skipped after exhausting
retries — a Cloud Monitoring log-based alert (set up at deploy time) watches
for that string and emails the user.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

import config
import generate
import idiom_generate
import idiom_prompt
import idiom_topics
import images
import poster
import state
import topic_generate
import validate
from idiom_images import IdiomImageError
from images import ImageSourcingError
from validate_prompt import build_retry_hint, build_rule_retry_hint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("concept-bot")

app = Flask(__name__)

_idiom_bank_issues = idiom_topics.validate_idiom_bank()
if _idiom_bank_issues:
    logger.error("IDIOM_BANK_INVALID: %s", json.dumps(_idiom_bank_issues))
    raise RuntimeError(f"idiom_topics.py failed validate_idiom_bank(): {_idiom_bank_issues}")


def _opening_line(draft: str) -> str:
    first_sentence = draft.split(". ")[0]
    return first_sentence[:120]


def _minutes_since_last_post(recent: list) -> float | None:
    last_posted = next((h for h in recent if h.get("status") == "posted" and h.get("date")), None)
    if not last_posted:
        return None
    last_time = datetime.fromisoformat(last_posted["date"])
    return (datetime.now(timezone.utc) - last_time) / timedelta(minutes=1)


def run_pipeline(dry_run: bool) -> dict:
    recent = state.get_recent_history()
    recent_openings = [h["opening_line"] for h in recent if h.get("opening_line")]

    if not dry_run:
        minutes_since = _minutes_since_last_post(recent)
        if minutes_since is not None and minutes_since < config.MIN_MINUTES_BETWEEN_POSTS:
            logger.info(
                "Skipping: last successful post was %.1f min ago (< %d min guard) -- likely a "
                "duplicate trigger for the same slot.",
                minutes_since, config.MIN_MINUTES_BETWEEN_POSTS,
            )
            return {"status": "skipped_duplicate_guard", "minutes_since_last_post": round(minutes_since, 1)}

    topic = topic_generate.get_dynamic_topic(recent)
    if topic is None:
        # No fallback bank -- per explicit instruction, if nothing passes
        # the topic gate, the slot is skipped rather than posting something
        # from a static list. Same POST_SKIPPED alerting path as any other
        # exhausted-retries failure.
        logger.error("POST_SKIPPED: %s", json.dumps({"reason": "topic generation exhausted, no topic gated a pass"}))
        if not dry_run:
            state.record_post({"status": "skipped", "reasons": ["topic generation exhausted"]})
        return {"status": "skipped", "reasons": ["topic generation exhausted"]}

    failure_reasons: list[str] = []
    retry_hint = ""

    for attempt in range(1, config.MAX_GENERATION_ATTEMPTS + 1):
        logger.info("Attempt %d/%d for topic '%s'", attempt, config.MAX_GENERATION_ATTEMPTS, topic["id"])

        draft = generate.generate_draft(topic, recent_openings, retry_hint)
        passed, reasons, scores = validate.validate_draft(draft, topic, recent_openings)
        state.record_draft(topic["id"], topic["category"], passed, reasons, scores)
        if not passed:
            failure_reasons = reasons
            # Never leave this empty on a failure -- an empty hint means the
            # next attempt sees an identical prompt and reproduces the same
            # violation. scores is None for a rule-based rejection (no critic
            # call was made), so fall back to the deterministic reasons.
            retry_hint = build_retry_hint(scores) if scores else build_rule_retry_hint(reasons)
            logger.info("Draft failed validation: %s", reasons)
            continue

        try:
            image = images.source_image(topic)
        except ImageSourcingError as e:
            # No fallback bank to re-pick from -- generate a fresh candidate
            # topic instead (its own gate applies again) rather than retrying
            # the same topic's image, which would likely fail identically for
            # a photo-type search.
            failure_reasons = [f"image sourcing failed: {e}"]
            logger.info("Image sourcing failed: %s -- generating a new candidate topic", e)
            new_topic = topic_generate.get_dynamic_topic(recent)
            if new_topic is None:
                break
            topic = new_topic
            retry_hint = ""
            continue

        opening_line = _opening_line(draft)

        if dry_run:
            return {
                "status": "dry_run",
                "topic": topic["id"],
                "category": topic["category"],
                "text": draft,
                "image_path": image.path,
                "image_source": image.source,
                "attribution": image.attribution,
            }

        tweet_id = poster.post(draft, image.path)
        state.record_post(
            {
                "topic_id": topic["id"],
                "category": topic["category"],
                "status": "posted",
                "tweet_id": tweet_id,
                "image_source": image.source,
                "attribution": image.attribution,
                "opening_line": opening_line,
                # Every post now stores its own descriptive text directly --
                # future novelty digests never depend on a static file.
                "topic_prompt": topic["prompt"],
            }
        )
        logger.info("Posted tweet %s for topic '%s'", tweet_id, topic["id"])
        return {"status": "posted", "tweet_id": tweet_id, "topic": topic["id"]}

    logger.error(
        "POST_SKIPPED: %s",
        json.dumps({"topic": topic["id"], "category": topic["category"], "reasons": failure_reasons}),
    )
    if not dry_run:
        state.record_post(
            {
                "topic_id": topic["id"],
                "category": topic["category"],
                "status": "skipped",
                "reasons": failure_reasons,
            }
        )
    return {"status": "skipped", "topic": topic["id"], "reasons": failure_reasons}


def run_idiom_pipeline(dry_run: bool, idiom_id: str | None = None) -> dict:
    """Idiom-format counterpart of run_pipeline. Parallel by design — the
    five-beat path above is untouched.

    DELIBERATE DIFFERENCE from the five-beat pipeline: an image failure here
    (Gemini refusal, quota, bad response) ships the post TEXT-ONLY instead of
    skipping the slot or re-picking the topic. The origin story carries the
    post; the engraving is a bonus.
    """
    recent = state.get_recent_history()

    if not dry_run:
        minutes_since = _minutes_since_last_post(recent)
        if minutes_since is not None and minutes_since < config.MIN_MINUTES_BETWEEN_POSTS:
            logger.info(
                "Skipping idiom post: last successful post was %.1f min ago (< %d min guard).",
                minutes_since, config.MIN_MINUTES_BETWEEN_POSTS,
            )
            return {"status": "skipped_duplicate_guard", "minutes_since_last_post": round(minutes_since, 1)}

    if idiom_id:
        topic = idiom_topics.get_idiom(idiom_id)
        if topic is None:
            return {"status": "error", "reason": f"unknown idiom_id {idiom_id!r}"}
    else:
        topic = idiom_generate.pick_next_idiom(recent)
        if topic is None:
            return {"status": "error", "reason": "no eligible idiom in the bank"}

    failure_reasons: list[str] = []
    retry_hint = ""

    for attempt in range(1, config.MAX_GENERATION_ATTEMPTS + 1):
        logger.info("Idiom attempt %d/%d for '%s'", attempt, config.MAX_GENERATION_ATTEMPTS, topic["id"])

        draft = idiom_generate.generate_idiom_draft(topic, retry_hint)
        passed, reasons, scores = idiom_generate.validate_idiom_draft(draft, topic)
        state.record_draft(
            topic["id"], "idiom", passed, reasons, None,
            fmt="idiom",
            score_fields=idiom_prompt.log_fields(scores, passed, reasons) if scores else None,
        )
        if not passed:
            failure_reasons = reasons
            retry_hint = idiom_prompt.build_retry_hint(scores) if scores else build_rule_retry_hint(reasons)
            logger.info("Idiom draft failed validation: %s", reasons)
            continue

        # Image failure -> text-only post, never a skipped slot (see docstring).
        image_path: str | None = None
        image_error = ""
        try:
            image_path = idiom_generate.source_idiom_image(topic)
        except IdiomImageError as e:
            image_error = str(e)
            logger.warning("Idiom image failed, shipping text-only: %s", e)

        opening_line = _opening_line(draft)
        # Validation ran on the plain *asterisk* text; the posted version
        # carries the idiom in Unicode italics.
        final_text = idiom_generate.italicize_marked(draft)

        if dry_run:
            return {
                "status": "dry_run",
                "format": "idiom",
                "topic": topic["id"],
                "text": final_text,
                "image_path": image_path,
                "image_error": image_error,
                "critic_scores": idiom_prompt.log_fields(scores, passed, reasons) if scores else None,
            }

        tweet_id = poster.post(final_text, image_path)
        state.record_post(
            {
                "topic_id": topic["id"],
                "category": "idiom",
                "format": "idiom",
                "status": "posted",
                "tweet_id": tweet_id,
                "image_source": "gemini-illustration" if image_path else "none",
                "attribution": "",
                "opening_line": opening_line,
            }
        )
        logger.info("Posted idiom tweet %s for '%s'", tweet_id, topic["id"])
        return {"status": "posted", "format": "idiom", "tweet_id": tweet_id, "topic": topic["id"],
                "text_only": image_path is None}

    logger.error(
        "POST_SKIPPED: %s",
        json.dumps({"format": "idiom", "topic": topic["id"], "reasons": failure_reasons}),
    )
    if not dry_run:
        state.record_post(
            {
                "topic_id": topic["id"],
                "category": "idiom",
                "format": "idiom",
                "status": "skipped",
                "reasons": failure_reasons,
            }
        )
    return {"status": "skipped", "format": "idiom", "topic": topic["id"], "reasons": failure_reasons}


@app.route("/post", methods=["GET", "POST"])
def post_endpoint():
    dry_run = request.args.get("dry_run", "false").lower() == "true"
    fmt = request.args.get("format", "everyday")
    if fmt == "idiom":
        result = run_idiom_pipeline(dry_run, idiom_id=request.args.get("idiom_id"))
    else:
        result = run_pipeline(dry_run)
    return jsonify(result), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Running locally -> http://127.0.0.1:{port}/post?dry_run=true")
    app.run(host="0.0.0.0", port=port, debug=True)
