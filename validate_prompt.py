"""
concept-bot validation gate — v2.

Drop-in replacement for the critic layer inside validate.py.
The rule-based layer from v1 stays as-is and still runs first (fails fast,
no API call). This file replaces the Claude critic pass that runs after it.

WHAT CHANGED FROM v1
--------------------
v1's critic asked a fuzzy question: "does this match the voice?" That check
passes fluent, well-written, unshareable posts — which is exactly what the
account was producing.

v2 scores five specific axes, all of which must clear threshold. The decisive
one is RETELLABILITY: the critic must be able to *extract the actual sentence*
a reader would repeat. If it cannot find that sentence, the post fails, no
matter how well written it is. That single gate does most of the work.

MODEL
-----
claude-haiku-4-5-20251001, thinking disabled, max_tokens ~600.
Cheap enough to run on every draft, and up to MAX_GENERATION_ATTEMPTS times.
"""

from __future__ import annotations

import json
import re


# --------------------------------------------------------------------------
# Thresholds
# --------------------------------------------------------------------------
# Tuned deliberately strict. A skipped slot costs nothing; a mediocre post
# costs distribution on every future post, because per-post engagement rate
# is what the ranking system actually scores the account on.
#
# Retune these in week 6 against real outcome data, not intuition.

THRESHOLDS = {
    "universality": 8,
    "prediction_violation": 7,
    "fluency": 8,
    "arousal": 7,
    "retellability": 8,
}

# If the critic cannot quote a dinner-table sentence, fail regardless of scores.
REQUIRE_EXTRACTED_GIFT = True


CRITIC_SYSTEM_PROMPT = """You are a ruthless editor for an X account that explains one everyday mystery per post.

You are not checking whether the post is good writing. Plenty of good writing gets ignored. You are checking whether it will actually travel, and travel means one specific thing: a tired stranger stops scrolling, finishes it, feels cleverer, and can retell it tonight.

Score the draft on five axes, 1 to 10. Be harsh. A 7 means "fine." Reserve 9 and 10 for drafts you would genuinely expect strangers to share.

# 1. UNIVERSALITY
Has essentially every human — any age, any education, any country, any job, possibly reading in a second language — *personally lived* the experience in the opening line?

Not "could they understand it." Have they *lived* it.

Score 10 only if a subsistence farmer, a teenager, and a retiree in three different countries have all personally lived it. Score 5 if it requires living in a developed country. Score 1 if it requires domain membership.

If the opening names a technical term, or assumes the reader belongs to a profession, hobby, or field, the ceiling is 3. No exceptions, no matter how well it is explained afterwards.

# 2. PREDICTION VIOLATION
Does the post break an assumption the reader confidently held? A fact the reader simply didn't know is not a violation. The reveal must contradict something they would have bet on.

10 = "the fridge is the worst place for bread"
7  = "ice is cloudy because of trapped air"
3  = "here is how a thing works" with nothing overturned

# 3. FLUENCY
Effort cost of entry. Is the first line twelve words or fewer? Is every term explained before it is used? Could someone exhausted, or reading in a second language, get through it without re-reading a sentence?

Any unexplained jargon anywhere caps this at 4. A first line over fifteen words caps it at 5.

# 4. AROUSAL
Does it produce "whoa," or merely "hm, noted"? Only high-arousal reactions travel — surprise, amusement, awe, mild alarm. Calm interest does not move a thumb.

Score what a stranger feels, not what a curious person feels.

# 5. RETELLABILITY
This is the decisive one: find the single sentence the reader would repeat at dinner tonight, and quote it back verbatim from the draft.

A qualifying sentence is one a person could say aloud, unprompted, to someone who has not read the post, and be understood. It is typically 8 to 24 words. It may contain a dash, a comma, or a colon — internal punctuation does not make it two sentences. It ends at the first sentence-ending mark. It very often IS the closing line of the post, because that is where the structure puts it. Look there first.

If no such sentence exists — if the insight is spread across three sentences, or needs setup to make sense, or is merely a definition — the draft fails. Say so plainly and leave the quote empty.

Returning empty when a qualifying sentence exists is as serious an error as passing a bad draft. Do not return empty merely because no sentence is outstanding — return empty only when none can stand alone.

The quote must be one self-contained sentence, under 25 words, that works with zero context. If it needs setup, spans more than one sentence, or is merely a definition, score it low and say so — don't round up because the surrounding draft is well written.

# Also check, and fail outright regardless of scores:
- Visible structure: headers, labels, bullets, numbered steps
- Emoji or hashtags
- An invented study, statistic, date, or named source, or a suspiciously specific figure
- Folklore stated as flat fact without hedging
- Engagement bait, a call to action, or a closing question that feels solicited
- An opening that repeats the shape of one of the recent openings supplied

Write your reasoning before you commit to any number. Reasoning-then-score forces the score to follow from the judgment; score-then-reasoning just rationalizes whatever number you already anchored on.

When you quote an excerpt from the draft *inside a larger sentence of your own* in `assessment`, `hard_failures`, or `fix`, wrap that excerpt in single quotes, never double quotes. A literal " inside a JSON string must be escaped, and this is the most common way your output becomes invalid — single quotes sidestep it entirely.

`dinner_table_sentence` is different: it is not prose containing a quote, it IS the quote. Its value must be the raw excerpt exactly as it appears in the draft, character for character, with no quotation marks added around it — the JSON string delimiters already mark it as a string. Wrapping it in extra quote marks of any kind breaks the verbatim match this whole gate depends on.

Return ONLY a JSON object, no other text, no markdown fences. `assessment` comes first, before any scores:

{
  "assessment": "<what the opening line assumes the reader has lived; what belief the reveal overturns; then the retellability search: list every sentence in the draft that could stand alone unprompted (check the closing line first — that is very often where it is), pick the strongest one, and only declare the list genuinely empty if none can stand alone>",
  "universality": <int>,
  "prediction_violation": <int>,
  "fluency": <int>,
  "arousal": <int>,
  "retellability": <int>,
  "dinner_table_sentence": "<the raw excerpt, verbatim from the draft, character for character, with no quotation marks added around it — or an empty string>",
  "hard_failures": ["<short reason>", ...],
  "weakest_link": "<the one axis to fix>",
  "fix": "<one concrete sentence of direction for the rewrite>"
}"""


def build_critic_user_turn(draft: str, topic: dict, recent_openings: list[str]) -> str:
    """Build the critic's user turn for one draft."""
    openings_block = (
        "\n".join(f"- {o}" for o in recent_openings)
        if recent_openings
        else "- (none yet)"
    )

    return f"""INTENDED UNIVERSAL DOOR (what the opening was supposed to enter through)
{topic['universal_door']}

INTENDED FEELING
{topic['emotion']}

RECENT OPENINGS (the draft must not repeat their shape)
{openings_block}

DRAFT
---
{draft}
---

Score it."""


# --------------------------------------------------------------------------
# Result handling
# --------------------------------------------------------------------------

def parse_critic_response(raw: str) -> dict:
    """
    Parse the critic's JSON. Tolerates stray markdown fences, since a parse
    failure would otherwise silently skip a slot.
    """
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def evaluate(scores: dict) -> tuple[bool, list[str]]:
    """
    Apply thresholds. Returns (passed, reasons_for_failure).

    `scores` is the parsed critic output.
    """
    reasons: list[str] = []

    for failure in scores.get("hard_failures") or []:
        reasons.append(f"hard: {failure}")

    for axis, floor in THRESHOLDS.items():
        value = scores.get(axis)
        if value is None:
            reasons.append(f"{axis}: missing from critic response")
        elif value < floor:
            reasons.append(f"{axis}: {value} < {floor}")

    if REQUIRE_EXTRACTED_GIFT and not (scores.get("dinner_table_sentence") or "").strip():
        reasons.append("no retellable sentence could be extracted")

    return (len(reasons) == 0, reasons)


def log_fields(scores: dict, passed: bool, reasons: list[str]) -> dict:
    """
    Flatten a critic result for Firestore. Store this on EVERY draft, including
    rejected ones.

    This is the dataset that makes week 6 possible: correlating critic scores
    against real impressions tells you whether the gate predicts reality. If it
    doesn't correlate, the thresholds are wrong and should be retuned from data
    rather than argued about.
    """
    return {
        "critic_universality": scores.get("universality"),
        "critic_prediction_violation": scores.get("prediction_violation"),
        "critic_fluency": scores.get("fluency"),
        "critic_arousal": scores.get("arousal"),
        "critic_retellability": scores.get("retellability"),
        "critic_gift": scores.get("dinner_table_sentence", ""),
        "critic_weakest_link": scores.get("weakest_link", ""),
        "critic_fix": scores.get("fix", ""),
        "critic_passed": passed,
        "critic_failure_reasons": reasons,
    }


def build_retry_hint(scores: dict) -> str:
    """
    Feed the critic's diagnosis back into the next generation attempt.

    v1 retried blind, so attempt 3 often repeated attempt 1's mistake. Append
    this to the user turn on retries.
    """
    weakest = scores.get("weakest_link", "")
    fix = scores.get("fix", "")
    if not (weakest or fix):
        return ""
    return (
        "\n\nA previous attempt was rejected."
        f"\nWeakest point: {weakest}"
        f"\nDirection: {fix}"
        "\nDo not simply reword the last attempt. Re-enter through the Door differently."
    )
