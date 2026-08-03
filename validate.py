"""Two-layer validation gate: cheap deterministic checks first, then a Claude
critic pass for tone/structure. Nothing gets posted without passing both.
"""
from __future__ import annotations

import json
import re

import anthropic

import config
from llm_utils import extract_text
from validate_prompt import (
    CRITIC_SYSTEM_PROMPT,
    build_critic_user_turn,
    evaluate,
    parse_critic_response,
)

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)

_LABEL_PATTERN = re.compile(
    r"^\s*(what it is|why it matters|the gotcha|the history|closing|hook)\s*:", re.IGNORECASE | re.MULTILINE
)
_BULLET_PATTERN = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)
_HEADER_PATTERN = re.compile(r"^#{1,6}\s", re.MULTILINE)
_SENTENCE_END_PATTERN = re.compile(r"[.!?]")
_GIFT_SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?]\s+[A-Z]")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_QUOTE_CHARS = "'\"‘’“”"


def _normalize_whitespace(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def _strip_wrapping_quotes(text: str) -> str:
    """The critic sometimes wraps dinner_table_sentence in its own quote marks
    (straight or curly) despite instructions not to. That's a formatting
    artifact, not paraphrasing — strip a matched leading/trailing quote pair
    before checking content, so this doesn't masquerade as a real gift_checks
    failure."""
    text = text.strip()
    if len(text) >= 2 and text[0] in _QUOTE_CHARS and text[-1] in _QUOTE_CHARS:
        text = text[1:-1].strip()
    return text


def rule_based_checks(draft: str) -> list[str]:
    violations = []

    if _LABEL_PATTERN.search(draft):
        violations.append("contains a visible section label (e.g. 'What it is:')")
    if _BULLET_PATTERN.search(draft):
        violations.append("contains bullet-point formatting instead of prose")
    if _HEADER_PATTERN.search(draft):
        violations.append("contains a markdown header")

    word_count = len(draft.split())
    if word_count < 40:
        violations.append(f"too short ({word_count} words) to match the required voice/depth")
    if word_count > 400:
        violations.append(f"too long ({word_count} words), likely to be truncated or lose focus")

    if draft and draft.rstrip()[-1] not in '.!?"”':
        violations.append("does not end on terminal punctuation — looks cut off mid-sentence")

    # Deterministic check on the opening line's effort cost — the critic scored
    # a 30-word opening 9/10 on fluency once even though its own rubric caps
    # that at 5. Countable properties don't get left to LLM judgment.
    match = _SENTENCE_END_PATTERN.search(draft)
    opening_line = draft[: match.start()] if match else draft
    opening_word_count = len(opening_line.split())
    if opening_word_count > 15:
        violations.append(
            f"opening line is {opening_word_count} words (max 15) — too expensive for a tired reader"
        )

    return violations


def critic_check(draft: str, topic: dict, recent_openings: list[str]) -> tuple[bool, list[str], dict]:
    user_prompt = build_critic_user_turn(draft, topic, recent_openings)

    # The critic occasionally emits an unescaped quote inside a JSON string
    # value, producing invalid JSON — a known LLM JSON-generation flake, not a
    # deterministic bug. Two retries (three attempts total) clear it in
    # practice; if all three fail, let the JSONDecodeError propagate rather
    # than silently treating the draft as passed or failed.
    last_error: json.JSONDecodeError | None = None
    for _ in range(3):
        resp = _client.messages.create(
            model=config.CRITIC_MODEL,
            max_tokens=600,
            thinking={"type": "disabled"},
            system=CRITIC_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = extract_text(resp)
        try:
            scores = parse_critic_response(text)
        except json.JSONDecodeError as e:
            last_error = e
            continue
        passed, reasons = evaluate(scores)
        return passed, reasons, scores

    raise last_error


def gift_checks(scores: dict, draft: str) -> list[str]:
    """Mechanically re-check the critic's extracted dinner_table_sentence.
    Retellability is the decisive gate, so its output can't rest on the
    critic's own say-so that a quote is "one sentence" or "verbatim" — those
    are countable properties, checked here instead of trusted."""
    violations = []
    sentence = _strip_wrapping_quotes((scores.get("dinner_table_sentence") or "").strip())
    if not sentence:
        return violations

    word_count = len(sentence.split())
    if word_count > 25:
        violations.append(f"extracted gift is {word_count} words — not a single retellable sentence")

    if len(_GIFT_SENTENCE_BOUNDARY_PATTERN.findall(sentence)) > 1:
        violations.append("extracted gift is multiple sentences")

    if _normalize_whitespace(sentence).lower() not in _normalize_whitespace(draft).lower():
        violations.append("critic paraphrased the gift instead of quoting it")

    return violations


def validate_draft(draft: str, topic: dict, recent_openings: list[str]) -> tuple[bool, list[str], dict | None]:
    """Returns (passed, reasons, scores). Runs rule-based checks first (cheap,
    no API call needed to fail fast), then the critic pass, then a mechanical
    re-check of the critic's own extracted gift.

    `scores` is None when the rule-based layer rejected the draft before any
    critic call was made; otherwise it's the critic's parsed score dict, for
    the caller to log and to build a retry hint from."""
    reasons = rule_based_checks(draft)
    if reasons:
        return False, reasons, None

    passed, reasons, scores = critic_check(draft, topic, recent_openings)

    gift_reasons = gift_checks(scores, draft)
    if gift_reasons:
        passed = False
        reasons = reasons + gift_reasons

    return passed, reasons, scores
