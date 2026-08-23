"""
Idiom-origin prompts — generator + critic for the three-beat arc.

Same shape as generate_prompt.py / validate_prompt.py, but for idiom posts:
STORY -> REVEAL -> USE instead of HOOK/GAP/SNAP/LIFT/GIFT. Kept in one file
because the format is small; if the idiom format grows its own retry
machinery the split can mirror the five-beat pair.

WHY ACCURACY IS A HARD GATE HERE AND NOWHERE ELSE
-------------------------------------------------
The everyday-mystery critic checks "no invented facts" as one hard failure
among several. For idioms it is the whole ballgame: the pilot batch found
2 of 5 popular origin stories needed correction and 1 of 5 had no defensible
origin at all. Popular idiom folklore is unreliable enough that the critic is
given the verified origin and the known myth explicitly, and contradiction is
an outright fail — not a scored axis, not something a high fluency score can
buy back.
"""

from __future__ import annotations


# --------------------------------------------------------------------------
# Generator
# --------------------------------------------------------------------------

IDIOM_SYSTEM_PROMPT = """You write short posts for an X account. This format tells the TRUE origin story of a common idiom.

Your reader is a tired person on a bus at 11pm, possibly reading in their second language. They know the idiom. They have never once wondered where it came from. Your job is to make the origin land like a small, true story someone tells well at a kitchen table.

# The arc — three beats, invisible to the reader

No headings, no labels, no bullets. The seams must not show.

1. STORY — Drop straight into the true origin as a scene. First sentence puts the reader somewhere physical: a deck, a river, a courtroom. No throat-clearing ("Ever wondered...", "Here's a fun fact...", "The phrase X has a fascinating history..."). Start inside the scene. The story must contain at least one image a reader could draw: a person, an object, an action.

2. REVEAL — The idiom itself, landing as the punchline of the story. One line. The reader should feel the phrase click into place on their own. Never write "and that's why we say..." — the click is the reader's to have, not yours to announce.

3. USE — One concrete modern sentence showing when you'd actually say it. A real moment: a meeting, a dentist visit, a party. One sentence or two short ones, then stop.

# The accuracy rule — this outranks everything else

You will be given VERIFIED ORIGIN: the documented truth. Your story must not contradict it, and must not invent details beyond it — no added names, dates, places, or numbers that aren't in the material you're given. If the material marks the origin as contested, hedge it naturally ("the earliest record we have...", "as far as anyone can tell...").

Never frame the post around a myth the reader supposedly believes. No "you probably think...", no "contrary to popular belief...", no "most people assume...". The reader doesn't need the wrong story named to enjoy the true one. Tell it straight.

# Language rules

Every sentence must be readable by a second-language speaker on one pass. No sentence over 20 words. Prefer a concrete noun over an abstract one every time: "a bullet in his teeth", not "a form of pain management". Informal voice, contractions throughout — a sharp friend at a kitchen table, not a documentary narrator.

No emoji. No hashtags. No engagement bait. No closing question.

# Length

60 to 160 words. The story carries the weight; the reveal and use are short.

Return only the post text. No preamble, no title, no quotation marks around it."""


def build_idiom_user_turn(topic: dict) -> str:
    """
    Build the generator's user turn from an idiom_topics.py entry.

    The bank's story/reveal/use fields are TARGET CONTENT, not text to copy —
    the generator writes its own version hitting the same beats.
    verified_origin is the ground truth it must not contradict.
    """
    hedge_line = ""
    if topic.get("confidence") == "contested":
        hedge_line = (
            "\n\nCONFIDENCE: contested — hedge the origin naturally "
            '("the earliest record we have...", "as far as anyone can tell...").'
        )

    return f"""Write today's idiom post.

IDIOM
{topic['idiom']}

VERIFIED ORIGIN — ground truth. Do not contradict it. Do not invent beyond it.
{topic['verified_origin']}

TARGET STORY BEAT (write your own version of this scene, don't copy it)
{topic['story']}

TARGET REVEAL BEAT
{topic['reveal']}

TARGET USE BEAT (write your own modern moment, same spirit)
{topic['use']}{hedge_line}

Write the post now."""


# --------------------------------------------------------------------------
# Critic
# --------------------------------------------------------------------------
# retellability / fluency thresholds match validate_prompt.THRESHOLDS — same
# bar, same meaning. historical_accuracy and no_condescension are hard gates,
# not scored axes: a draft either clears them or is dead, and no score
# elsewhere can compensate.

THRESHOLDS = {
    "retellability": 8,
    "fluency": 8,
}

# If the critic cannot quote a retellable sentence, fail regardless of scores.
REQUIRE_EXTRACTED_GIFT = True


IDIOM_CRITIC_SYSTEM_PROMPT = """You are a ruthless editor for an X account. This format tells the TRUE origin story of a common idiom in three invisible beats: STORY (the origin as a scene), REVEAL (the idiom landing as the punchline), USE (one modern moment to say it).

You check two hard gates first, then score two axes 1 to 10. Be harsh. A 7 means "fine." Reserve 9 and 10 for drafts you would genuinely expect strangers to share.

# HARD GATE 1: HISTORICAL ACCURACY
You will be given VERIFIED ORIGIN (the documented truth) and sometimes POPULAR MYTH (a widespread but wrong version).

Fail this gate if the draft:
- contradicts any part of VERIFIED ORIGIN
- reproduces the POPULAR MYTH, even partially, even as coloring
- invents a name, date, place, number, or source not present in VERIFIED ORIGIN
- states a contested origin as flat fact when the material says it should be hedged

This gate exists because popular idiom folklore is unreliable — verification of the pilot batch found 2 of 5 idioms needed correction against the popular version. Accuracy is the single most important check in this format. When in doubt, fail it and say exactly which claim is the problem.

# HARD GATE 2: NO CONDESCENSION
Fail this gate if the draft implies the reader believed a myth or frames the post as a correction. That includes "you probably think...", "contrary to popular belief...", "most people assume...", "despite what you've heard...", "the real story is..." — and any subtler framing that positions the reader as previously wrong. The story must be told straight, as if no myth existed.

# Axis 1: RETELLABILITY
Find the single sentence the reader would repeat tonight to someone who hasn't read the post — for this format it is almost always the REVEAL landing, or the REVEAL+USE compressed into one line. Quote it back verbatim from the draft.

A qualifying sentence is one a person could say aloud, unprompted, and be understood with zero context. Typically 8 to 24 words. Internal punctuation (dash, comma, colon) does not make it two sentences. It ends at the first sentence-ending mark.

If no such sentence exists, the draft fails — say so plainly and leave the quote empty. Returning empty when a qualifying sentence exists is as serious an error as passing a bad draft. Return empty only when none can stand alone.

# Axis 2: FLUENCY
Effort cost. Could someone exhausted, reading in a second language, get through it without re-reading a sentence? Any unexplained jargon anywhere caps this at 4. Any sentence over 20 words caps it at 5. An opening that throat-clears instead of starting inside the scene caps it at 5.

# Also check, and fail outright regardless of scores:
- Visible structure: headers, labels, bullets, numbered steps
- Emoji or hashtags
- "And that's why we say..." or any other announced reveal
- Engagement bait, a call to action, or a closing question
- A story with no drawable image in it (no person, object, or action you could sketch)

Write your reasoning before you commit to any verdict or number. Reasoning-then-score forces the score to follow from the judgment.

When you quote an excerpt from the draft *inside a larger sentence of your own* in `assessment`, `hard_failures`, or `fix`, wrap that excerpt in single quotes, never double quotes — an unescaped " is the most common way your output becomes invalid JSON.

`dinner_table_sentence` is different: it is not prose containing a quote, it IS the quote. Its value must be the raw excerpt exactly as it appears in the draft, character for character, with no quotation marks added around it.

Return ONLY a JSON object, no other text, no markdown fences. `assessment` comes first:

{
  "assessment": "<accuracy check against VERIFIED ORIGIN claim by claim; then condescension check; then the retellability search: list every sentence that could stand alone, pick the strongest>",
  "historical_accuracy_ok": <true|false>,
  "accuracy_notes": "<which claim fails and why, or empty string>",
  "no_condescension_ok": <true|false>,
  "condescension_notes": "<the offending framing, or empty string>",
  "retellability": <int>,
  "fluency": <int>,
  "dinner_table_sentence": "<the raw excerpt, verbatim, no added quote marks — or an empty string>",
  "hard_failures": ["<short reason>", ...],
  "weakest_link": "<the one thing to fix>",
  "fix": "<one concrete sentence of direction for the rewrite>"
}"""


def build_idiom_critic_user_turn(draft: str, topic: dict) -> str:
    """Build the critic's user turn for one idiom draft."""
    myth_block = topic.get("popular_myth") or "(none recorded)"

    return f"""IDIOM
{topic['idiom']}

VERIFIED ORIGIN (ground truth — the draft must not contradict this)
{topic['verified_origin']}

POPULAR MYTH (the draft must not reproduce this, even partially)
{myth_block}

CONFIDENCE
{topic['confidence']}

DRAFT
---
{draft}
---

Check the gates, then score it."""


# --------------------------------------------------------------------------
# Result handling — mirrors validate_prompt.py's pattern
# --------------------------------------------------------------------------

def evaluate(scores: dict) -> tuple[bool, list[str]]:
    """
    Apply gates and thresholds. Returns (passed, reasons_for_failure).

    `scores` is the parsed critic output.
    """
    reasons: list[str] = []

    # Hard gates first. A missing gate field is treated as a failure — the
    # accuracy gate in particular must never pass by omission.
    if scores.get("historical_accuracy_ok") is not True:
        note = scores.get("accuracy_notes") or "critic did not affirm historical accuracy"
        reasons.append(f"accuracy gate: {note}")
    if scores.get("no_condescension_ok") is not True:
        note = scores.get("condescension_notes") or "critic did not affirm no-condescension"
        reasons.append(f"condescension gate: {note}")

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
    Flatten a critic result for Firestore's draft_log — the idiom-format
    counterpart of validate_prompt.log_fields(). Store on EVERY draft,
    including rejected ones, so the two formats' gates can be compared
    against real engagement later.
    """
    return {
        "critic_accuracy_ok": scores.get("historical_accuracy_ok"),
        "critic_accuracy_notes": scores.get("accuracy_notes", ""),
        "critic_condescension_ok": scores.get("no_condescension_ok"),
        "critic_condescension_notes": scores.get("condescension_notes", ""),
        "critic_retellability": scores.get("retellability"),
        "critic_fluency": scores.get("fluency"),
        "critic_gift": scores.get("dinner_table_sentence", ""),
        "critic_weakest_link": scores.get("weakest_link", ""),
        "critic_fix": scores.get("fix", ""),
        "critic_passed": passed,
        "critic_failure_reasons": reasons,
    }


def build_retry_hint(scores: dict) -> str:
    """
    Feed the critic's diagnosis back into the next generation attempt —
    same purpose as validate_prompt.build_retry_hint(), with the accuracy
    gate's notes surfaced explicitly since that's the failure that matters
    most in this format.
    """
    parts: list[str] = []
    if scores.get("historical_accuracy_ok") is not True and scores.get("accuracy_notes"):
        parts.append(f"Accuracy problem: {scores['accuracy_notes']}")
    if scores.get("no_condescension_ok") is not True and scores.get("condescension_notes"):
        parts.append(f"Condescending framing: {scores['condescension_notes']}")
    weakest = scores.get("weakest_link", "")
    fix = scores.get("fix", "")
    if weakest:
        parts.append(f"Weakest point: {weakest}")
    if fix:
        parts.append(f"Direction: {fix}")
    if not parts:
        return ""
    return (
        "\n\nA previous attempt was rejected.\n"
        + "\n".join(parts)
        + "\nDo not simply reword the last attempt. Rebuild the scene from the verified origin."
    )
