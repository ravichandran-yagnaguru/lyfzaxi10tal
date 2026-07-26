"""Two-layer validation gate: cheap deterministic checks first, then a Claude
critic pass for tone/structure. Nothing gets posted without passing both.
"""
import re

import anthropic

import config

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

_LABEL_PATTERN = re.compile(
    r"^\s*(what it is|why it matters|the gotcha|the history|closing|hook)\s*:", re.IGNORECASE | re.MULTILINE
)
_BULLET_PATTERN = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)
_HEADER_PATTERN = re.compile(r"^#{1,6}\s", re.MULTILINE)
_YEAR_PATTERN = re.compile(r"\b(1[6-9]\d{2}|20\d{2})\b")
_HEDGE_PHRASES = [
    "legend has it", "the story goes", "some say", "as the story", "allegedly",
    "supposedly", "rumor has it", "the tale", "as legend", "as the tale",
]


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

    if _YEAR_PATTERN.search(draft):
        has_hedge = any(phrase in draft.lower() for phrase in _HEDGE_PHRASES)
        if not has_hedge:
            violations.append(
                "mentions a specific year/date with no hedging language — the critic pass must "
                "confirm this is genuinely well-documented history, not folklore stated as fact"
            )

    return violations


_CRITIC_SYSTEM_PROMPT = """You are a strict editor for a daily X (Twitter) concept-explainer \
account. You review ONE draft post against these rules and respond with a verdict.

Rules:
- Informal, whiteboard-explanation voice; contractions; short sentences mixed with one longer one.
- No jargon left undefined.
- No visible structure — no labels, no headers, no bullet points; reads as natural prose.
- If it states a historical claim as flat fact (specific date, named event) without hedging \
("legend has it", "the story goes", etc.), that's only acceptable if the claim is genuinely \
well-established, common knowledge (e.g. widely documented invention dates, published research). \
If it reads like unverifiable folklore stated as flat fact, that's a FAIL.
- Must not open the same way as any of the recent posts listed below.
- Must not be a repeat/rehash of the same rhetorical trick as the recent posts (e.g. always \
opening with "Ever wonder...").

Respond in EXACTLY this format, nothing else:
VERDICT: PASS or FAIL
REASON: one short sentence why (blank if PASS)"""


def critic_check(draft: str, recent_openings: list[str]) -> tuple[bool, str]:
    recent_block = "\n".join(f"- {o}" for o in recent_openings) or "(none yet)"
    user_prompt = f"Recent post openings to avoid repeating:\n{recent_block}\n\nDraft to review:\n{draft}"

    resp = _client.messages.create(
        model=config.CRITIC_MODEL,
        max_tokens=200,
        system=_CRITIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = resp.content[0].text.strip()

    verdict_match = re.search(r"VERDICT:\s*(PASS|FAIL)", text, re.IGNORECASE)
    reason_match = re.search(r"REASON:\s*(.*)", text, re.IGNORECASE)

    passed = bool(verdict_match) and verdict_match.group(1).upper() == "PASS"
    reason = reason_match.group(1).strip() if reason_match else ""
    return passed, reason


def validate_draft(draft: str, recent_openings: list[str]) -> tuple[bool, list[str]]:
    """Returns (passed, reasons). Runs rule-based checks first (cheap, no API
    call needed to fail fast), then the critic pass only if those pass."""
    reasons = rule_based_checks(draft)
    if reasons:
        return False, reasons

    critic_passed, critic_reason = critic_check(draft, recent_openings)
    if not critic_passed:
        return False, [critic_reason or "failed critic review"]

    return True, []
