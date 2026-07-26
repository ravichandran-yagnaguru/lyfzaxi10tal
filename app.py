"""Cloud Run entrypoint. One endpoint, /post, invoked by Cloud Scheduler (or
manually for testing). Orchestrates: pick topic -> generate + validate
(retrying) -> source image -> post -> record state.

Logs a POST_SKIPPED error line when a day is skipped after exhausting
retries — a Cloud Monitoring log-based alert (set up at deploy time) watches
for that string and emails the user.
"""
import json
import logging
import os

from flask import Flask, jsonify, request

import config
import generate
import images
import poster
import state
import topics
import validate
from images import ImageSourcingError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("concept-bot")

app = Flask(__name__)


def _opening_line(draft: str) -> str:
    first_sentence = draft.split(". ")[0]
    return first_sentence[:120]


def run_pipeline(dry_run: bool) -> dict:
    recent = state.get_recent_history()
    recent_openings = [h["opening_line"] for h in recent if h.get("opening_line")]

    topic = topics.pick_next_topic(recent)
    failure_reasons: list[str] = []

    for attempt in range(1, config.MAX_GENERATION_ATTEMPTS + 1):
        logger.info("Attempt %d/%d for topic '%s'", attempt, config.MAX_GENERATION_ATTEMPTS, topic["id"])

        draft = generate.generate_draft(topic, recent_openings)
        passed, reasons = validate.validate_draft(draft, recent_openings)
        if not passed:
            failure_reasons = reasons
            logger.info("Draft failed validation: %s", reasons)
            continue

        try:
            image = images.source_image(topic)
        except ImageSourcingError as e:
            failure_reasons = [f"image sourcing failed: {e}"]
            logger.info("Image sourcing failed: %s", e)
            if topic["image_type"] == "photo":
                topic = topics.pick_next_topic(recent)
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


@app.route("/post", methods=["GET", "POST"])
def post_endpoint():
    dry_run = request.args.get("dry_run", "false").lower() == "true"
    result = run_pipeline(dry_run)
    return jsonify(result), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Running locally -> http://127.0.0.1:{port}/post?dry_run=true")
    app.run(host="0.0.0.0", port=port, debug=True)
