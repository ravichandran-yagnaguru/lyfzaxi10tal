"""
Idiom-format pipeline pieces: generation, validation, selection, image.

Parallel to generate.py + validate.py for the five-beat everyday-mystery
format — deliberately a separate module so the existing pipeline stays
completely untouched. Shared, format-agnostic helpers (rule_based_checks,
gift_checks, parse_critic_response) are imported rather than duplicated.
"""

from __future__ import annotations

import json
import random
import re

import anthropic

import config
import idiom_images
import idiom_prompt
import idiom_research
import idiom_topics
from idiom_topics import IDIOM_TOPICS
from llm_utils import extract_text
from validate import gift_checks, rule_based_checks
from validate_prompt import parse_critic_response

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)


def find_idiom(idiom_id: str, queue: list[dict]) -> dict | None:
    """Look an idiom up by id in the hand-researched bank, then the queue."""
    return idiom_topics.get_idiom(idiom_id) or next((q for q in queue if q.get("id") == idiom_id), None)


def pick_next_idiom(idiom_history: list[dict], queue: list[dict], exclude_ids: set = frozenset()) -> dict | None:
    """
    Pick the next idiom to post. NEVER returns an idiom that has already
    been posted -- when nothing unposted is left, returns None and the caller
    skips the slot (same rule as everyday topics: skip, don't repeat).

    The previous version recycled the least-recently-posted idiom once the
    30-entry bank was exhausted. At 2 posts/day that happened on 2026-09-28,
    and white elephant, steal thunder, rule of thumb and saved by the bell
    all posted a second time. A finite bank plus a repeat-on-exhaustion
    fallback quietly broke the "100% no repeated post" rule.

    Order of preference:
      1. hand-researched bank idioms never posted (verified, scenes written
         by hand) -- includes ones that failed the draft gate once
      2. the oldest idiom in the researched queue (see idiom_research.py)

    An idiom whose draft has failed the quality gate MAX_ATTEMPTS_PER_IDIOM
    times is given up on, not retried forever. `idiom_history` is the FULL
    idiom record from state.get_idiom_history() -- a windowed view would
    quietly forget old idioms.
    """
    posted = {h.get("topic_id") for h in idiom_history if h.get("status") == "posted"}
    skips: dict[str, int] = {}
    for h in idiom_history:
        if h.get("status") == "skipped" and h.get("topic_id"):
            skips[h["topic_id"]] = skips.get(h["topic_id"], 0) + 1

    def usable(topic_id: str) -> bool:
        return (
            topic_id not in posted
            and topic_id not in exclude_ids
            and skips.get(topic_id, 0) < idiom_research.MAX_ATTEMPTS_PER_IDIOM
        )

    from_bank = [t for t in IDIOM_TOPICS if usable(t["id"])]
    if from_bank:
        return random.choice(from_bank)

    ready = [q for q in queue if q.get("status") == "ready" and usable(q["id"])]
    return ready[0] if ready else None  # queue is oldest-first


# X has no native italics; the convention is Unicode Mathematical Sans-Serif
# Italic letters. The generator marks the idiom with *asterisks* (validated
# mechanically below), and this converts those spans right before posting —
# validation always runs on the plain-asterisk text so verbatim checks and
# critic quotes stay trivially comparable.
_ITALIC_UPPER_OFFSET = 0x1D608 - ord("A")
_ITALIC_LOWER_OFFSET = 0x1D622 - ord("a")
_MARKED_SPAN = re.compile(r"\*([^*\n]+)\*")


def _to_italic_unicode(text: str) -> str:
    out = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr(ord(ch) + _ITALIC_UPPER_OFFSET))
        elif "a" <= ch <= "z":
            out.append(chr(ord(ch) + _ITALIC_LOWER_OFFSET))
        else:
            out.append(ch)
    return "".join(out)


def italicize_marked(text: str) -> str:
    """Replace every *marked span* with Unicode italic characters."""
    return _MARKED_SPAN.sub(lambda m: _to_italic_unicode(m.group(1)), text)


def idiom_rule_checks(draft: str, topic: dict) -> list[str]:
    """Deterministic checks for the four-beat structure — the parts of the
    nothing-to-guess gate that are countable don't rest on the critic's
    judgment (same principle as validate.gift_checks)."""
    violations = []
    first_line = draft.strip().splitlines()[0] if draft.strip() else ""

    if f"*{topic['idiom'].lower()}*" not in first_line.lower():
        violations.append(
            f"first line must name the idiom wrapped in asterisks: *{topic['idiom']}*"
        )
    if not re.search(r'["“][^"“”]{5,}["”]', draft):
        violations.append("no quoted usage example found (the USE beat must be a quoted sentence)")
    return violations


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
    reasons = rule_based_checks(draft) + idiom_rule_checks(draft, topic)
    if reasons:
        return False, reasons, None

    passed, reasons, scores = critic_check(draft, topic)

    gift_reasons = gift_checks(scores, draft)
    if gift_reasons:
        passed = False
        reasons = reasons + gift_reasons

    return passed, reasons, scores


def source_idiom_image(topic: dict) -> str:
    """Generate the engraving-style illustration for this idiom, then verify
    it actually depicts the bank's scene (a cheap Haiku vision check — Gemini
    occasionally drifts off-prompt, and an off-topic image under a history
    post costs credibility). One regeneration attempt if the first image
    fails relevance; after that, raise. Raises idiom_images.IdiomImageError
    on any failure — the caller ships the post text-only in that case
    (deliberately different from the five-beat pipeline, where image failure
    skips/re-picks)."""
    era = topic.get("era", "19th")
    last_reason = ""
    for attempt in range(2):
        path = idiom_images.generate_idiom_image(topic["id"], era, topic["image_style"])
        relevant, reason = idiom_images.check_image_relevance(path, topic["image_style"])
        if relevant:
            return path
        last_reason = reason
    raise idiom_images.IdiomImageError(
        f"generated image failed relevance check twice: {last_reason}"
    )
