"""
Idiom-format pipeline pieces: generation, validation, selection, image.

Parallel to generate.py + validate.py for the five-beat everyday-mystery
format — deliberately a separate module so the existing pipeline stays
completely untouched. Shared, format-agnostic helpers (rule_based_checks,
gift_checks, parse_critic_response) are imported rather than duplicated.
"""

from __future__ import annotations

import json

import anthropic

import config
import idiom_images
import idiom_prompt
from idiom_topics import IDIOM_TOPICS
from llm_utils import extract_text
from validate import gift_checks, rule_based_checks
from validate_prompt import parse_critic_response

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)

# Era per idiom for the engraving-style image prompt. idiom_topics.py doesn't
# store era separately from the scene description (see generate_for_topic's
# docstring) — this mapping mirrors the values the pilot images were
# generated with. New idioms without an entry fall back to 19th century.
IDIOM_ERAS = {
    "bite_the_bullet": "18th",
    "break_the_ice": "19th",
    "caught_red_handed": "15th",
}


def pick_next_idiom(recent_history: list[dict], exclude_ids: set = frozenset()) -> dict | None:
    """
    Pick the next idiom to post. recent_history is the same most-recent-first
    post_history the everyday-mystery picker reads; idiom entries are the ones
    whose topic_id is in the idiom bank (ids don't collide with topics.py).

    Only "solid"/"contested"-confidence idioms are eligible (validate_idiom_bank
    enforces that "unknown" never even loads). Prefers never-posted idioms in
    bank order; once all have posted, returns the least recently posted.
    Returns None only if every idiom is excluded.
    """
    eligible = [
        t for t in IDIOM_TOPICS
        if t["confidence"] in ("solid", "contested") and t["id"] not in exclude_ids
    ]
    if not eligible:
        return None

    posted_order = [h["topic_id"] for h in recent_history]  # most-recent-first

    def last_used_index(topic: dict) -> int:
        try:
            return posted_order.index(topic["id"])
        except ValueError:
            return -1  # never used

    never_used = [t for t in eligible if last_used_index(t) == -1]
    if never_used:
        return never_used[0]
    return max(eligible, key=last_used_index)


def generate_idiom_draft(topic: dict, retry_hint: str = "") -> str:
    user_turn = idiom_prompt.build_idiom_user_turn(topic) + retry_hint

    resp = _client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=1024,
        thinking={"type": "disabled"},
        system=[{
            "type": "text",
            "text": idiom_prompt.IDIOM_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_turn}],
    )
    return extract_text(resp)


def critic_check(draft: str, topic: dict) -> tuple[bool, list[str], dict]:
    """Same JSON-flake retry shape as validate.critic_check: up to three
    attempts to get parseable JSON, then let the error propagate."""
    user_prompt = idiom_prompt.build_idiom_critic_user_turn(draft, topic)

    last_error: json.JSONDecodeError | None = None
    for _ in range(3):
        # 1500, not the five-beat critic's 600: the idiom critic's assessment
        # walks VERIFIED ORIGIN claim by claim before scoring, which is longer
        # prose. 700 was observed truncating mid-JSON (stop_reason=max_tokens).
        resp = _client.messages.create(
            model=config.CRITIC_MODEL,
            max_tokens=1500,
            thinking={"type": "disabled"},
            system=idiom_prompt.IDIOM_CRITIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = extract_text(resp)
        try:
            scores = parse_critic_response(text)
        except json.JSONDecodeError as e:
            last_error = e
            continue
        passed, reasons = idiom_prompt.evaluate(scores)
        return passed, reasons, scores

    raise last_error


def validate_idiom_draft(draft: str, topic: dict) -> tuple[bool, list[str], dict | None]:
    """Rule-based checks (shared with the five-beat format — labels, bullets,
    word bounds, opening-line cost) first, then the idiom critic, then the
    same mechanical gift re-check the five-beat gate uses (the critic's
    extracted sentence must be verbatim and singular — same key name,
    dinner_table_sentence, so gift_checks applies unchanged)."""
    reasons = rule_based_checks(draft)
    if reasons:
        return False, reasons, None

    passed, reasons, scores = critic_check(draft, topic)

    gift_reasons = gift_checks(scores, draft)
    if gift_reasons:
        passed = False
        reasons = reasons + gift_reasons

    return passed, reasons, scores


def source_idiom_image(topic: dict) -> str:
    """Generate the engraving-style illustration for this idiom. Returns the
    local file path. Raises idiom_images.IdiomImageError on any failure —
    the caller ships the post text-only in that case (deliberately different
    from the five-beat pipeline, where image failure skips/re-picks)."""
    era = IDIOM_ERAS.get(topic["id"], "19th")
    return idiom_images.generate_idiom_image(topic["id"], era, topic["image_style"])
