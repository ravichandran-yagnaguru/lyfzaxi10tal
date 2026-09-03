"""
Dynamic topic generation for the everyday-mystery format.

WHY THIS EXISTS
----------------
The old topics.py bank was a hand-curated 54-item list, and at ~2 posts/day
it fully cycled in about a month -- after that, every "new" post was
necessarily a repeat of one of the same 54 ideas, just reshuffled. Guru
reported the feed "feels redundant"; auditing Firestore found no
duplicate-id or racing bug (the earlier tie-break fix was still holding,
gaps between id repeats matched a fair full-cycle length) -- the bank's IDEA
SPACE was finite, not the code. A fixed list, however well written, has a
ceiling.

This module removes the ceiling entirely: there is no fallback bank. Every
post generates a fresh candidate topic, gated for quality, or the slot is
skipped -- same as any other validation failure in this pipeline. Per
Guru's explicit instruction: "if AI is not able to pick anything pass the
gate, we don't want to post, rather than picking up from the bank."

The discipline the old bank enforced is kept even though the bank itself is
gone: the original v1 engine let the model pick a subject and write about it
freely, and it produced things like "sharding" -- technically correct,
universally unreadable, because nothing forced a real Universal Door.
Free-generating topics without structure would risk that same failure mode
reappearing, so every candidate is still held to the identical schema the
bank used to enforce, and still passes a dedicated gate before any drafting
happens.

THE PIPELINE
------------
1. build_recent_topics_digest() -- pulls real post history as the novelty
   baseline. Every post_history record (bank-origin posts from before this
   change, migrated once; every dynamically-generated post going forward)
   stores its own `topic_prompt` text directly, so this never depends on a
   static file -- it only ever reads Firestore.
2. generate_candidate() -- one Claude Sonnet call proposing ONE new topic in
   the schema below, explicitly shown the digest and told not to duplicate
   the underlying phenomenon of anything in it.
3. topic_gate_check() -- one Claude Haiku call, separate from the draft
   critic, checking the candidate itself (not a draft) on three axes before
   any expensive generation happens: genuine Universal Door (not
   subject-first), factual plausibility, and semantic novelty vs the digest.
4. get_dynamic_topic() -- orchestrates 1-3 with MAX_TOPIC_ATTEMPTS retries.
   Returns None if nothing passes -- the caller (app.py) must treat that as
   a skipped slot, not reach for a substitute.
"""

from __future__ import annotations

import json
import logging
import re

import anthropic

import config
from llm_utils import extract_text

logger = logging.getLogger("concept-bot")

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)

# Fixed vocabulary a candidate's category/emotion must come from -- kept
# stable (not derived from any file) so categorization stays comparable over
# time even though the topic content itself is now unbounded.
CATEGORIES = ["body", "everyday", "history", "money", "psychology", "science", "tech"]
EMOTIONS = ["surprise", "amusement", "alarm", "awe", "wrong"]

# Observed empirically: the gate (deliberately as strict as the rest of this
# account's validation) rejects roughly 2 of 3 candidates -- 3 attempts
# sometimes exhausted without a pass in local testing. 6 attempts costs a
# few more cents per post but meaningfully raises the odds of landing a
# genuinely new, genuinely universal topic before the slot is skipped.
MAX_TOPIC_ATTEMPTS = 6
DIGEST_LIMIT = 80

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_PATTERN.sub("_", text.lower()).strip("_")
    return f"gen_{slug[:40]}" if slug else "gen_topic"


# --------------------------------------------------------------------------
# Digest: the real novelty baseline, pulled from actual post history
# --------------------------------------------------------------------------

def build_recent_topics_digest(limit: int = DIGEST_LIMIT) -> list[dict]:
    """Most-recent-first list of {"id", "category", "description"} covering
    every distinct everyday-format topic actually posted recently, read
    entirely from Firestore's `topic_prompt` field on each post_history
    record (every dynamically-generated post stores its own; historical
    bank-origin posts were migrated once when the bank was retired). Skips
    idiom-format entries (different bank, different novelty space)."""
    import state

    recent = state.get_recent_history(limit)
    digest: list[dict] = []
    seen_ids: set[str] = set()

    for h in recent:
        if h.get("format") == "idiom":
            continue
        tid = h.get("topic_id")
        if not tid or tid in seen_ids:
            continue
        seen_ids.add(tid)

        description = h.get("topic_prompt")
        if description:
            digest.append({"id": tid, "category": h.get("category", ""), "description": description})

    return digest


def _digest_block(digest: list[dict]) -> str:
    if not digest:
        return "(no post history yet -- anything genuinely universal is fair game)"
    return "\n".join(f"- [{d['category']}] {d['description']}" for d in digest)


# --------------------------------------------------------------------------
# Step 1: candidate generation
# --------------------------------------------------------------------------

_BRAINSTORM_SYSTEM_PROMPT = f"""You propose ONE new topic for an X account that explains one everyday mystery per post, in the exact shape of a curated topic bank -- not a free subject, a fully-specified entry.

# The Universal Door -- the non-negotiable rule

Every concept has many entry points. Almost all are locked to a subgroup (an education level, a profession, a country). The Door is the one entry point that essentially every human has personally walked through -- a nurse, a farmer, a teenager, a retiree, in any country, reading in a second language.

BAD topic: "sharding" -- entered through the technical term, aimed at people who already know it.
GOOD topic: the moment two billion people open Instagram at breakfast and it doesn't collapse -- then sharding is the mechanism underneath, never the entry point.

Reject any candidate where the honest answer to "has a person with zero education in this subject personally lived the opening line" is no.

# What you must produce -- exact schema, all fields required

- id: a short lowercase snake_case slug, 2-4 words, unique-sounding
- category: EXACTLY one of: {", ".join(CATEGORIES)}
- prompt: the actual mechanism/fact being explained, one or two sentences, written for someone who will draft a post from it (not the post itself)
- universal_door: the lived experience that is the ONLY permitted entry point -- one sentence, concrete, something a reader has personally done or felt
- hook_seed: a seed for the opening line, 12 words or fewer, may be rephrased by the writer but must not raise the reading cost
- dinner_table_line: the retellable sentence this post must land -- close in spirit to what a reader would repeat at dinner tonight
- emotion: EXACTLY one of: {", ".join(EMOTIONS)}
- image_type: "diagram" if the concept is abstract/mechanism-based (illustrated), "photo" if it's a concrete physical object/scene (real photo) -- if "photo", also include photo_keywords (a search query) and photo_subject (the singular noun a photo's own description must mention)

# Ground rules

- The underlying fact must be genuinely well-known/plausible, not a coin-flip or an invented statistic. If you're not confident it's true, don't propose it.
- Never propose a topic whose UNDERLYING PHENOMENON substantially overlaps with anything in the ALREADY COVERED list you're given -- a different wording of the same idea still counts as a repeat.
- Prefer topics that are genuinely fresh territory: overlooked physical objects, body quirks, psychology effects, money/behavioral-economics moments, history/design origin stories, science that shows up in daily life. Avoid anything requiring specialist vocabulary to even state.

Return ONLY a JSON object, no other text, no markdown fences:

{{
  "id": "...",
  "category": "...",
  "prompt": "...",
  "universal_door": "...",
  "hook_seed": "...",
  "dinner_table_line": "...",
  "emotion": "...",
  "image_type": "diagram or photo",
  "photo_keywords": "... (omit or empty if image_type is diagram)",
  "photo_subject": "... (omit or empty if image_type is diagram)"
}}"""


def _parse_json_response(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def generate_candidate(digest: list[dict], last_category: str | None, retry_hint: str = "") -> dict:
    avoid_category_line = (
        f"\n\nDo not use category \"{last_category}\" -- that was the immediately preceding post's category."
        if last_category else ""
    )
    user_turn = (
        f"ALREADY COVERED (do not repeat the underlying idea of any of these)\n"
        f"{_digest_block(digest)}"
        f"{avoid_category_line}{retry_hint}\n\n"
        "Propose one new topic now."
    )

    resp = _client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=800,
        thinking={"type": "disabled"},
        system=[{"type": "text", "text": _BRAINSTORM_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_turn}],
    )
    candidate = _parse_json_response(extract_text(resp))

    if not candidate.get("id") or not re.fullmatch(r"[a-z0-9_]+", candidate.get("id", "")):
        candidate["id"] = _slugify(candidate.get("prompt", "topic"))
    candidate["id"] = f"gen_{candidate['id']}" if not candidate["id"].startswith("gen_") else candidate["id"]
    return candidate


# --------------------------------------------------------------------------
# Step 2: topic gate -- checks the CANDIDATE, before any draft is written
# --------------------------------------------------------------------------

_TOPIC_CRITIC_SYSTEM_PROMPT = """You are a strict gatekeeper for candidate topics proposed for an everyday-mystery X account. You check the PROPOSAL, not a finished post -- this runs before any drafting happens, to avoid wasting a generation attempt on a bad idea.

Check three things and be harsh:

# 1. GENUINE UNIVERSAL DOOR
Has essentially every human -- any age, any education, any country, possibly reading in a second language -- personally lived the `universal_door` experience? Not "could understand it" -- lived it. If the door requires domain membership, a specific culture, or specialist context, fail this.

# 2. FACTUAL PLAUSIBILITY
Is the `prompt` a genuinely well-established, plausible fact or mechanism -- not an invented statistic, a coin-flip claim, or something that sounds plausible but isn't actually verified common knowledge? If you're not confident it's true, fail this and say why.

# 3. NOVELTY
Compare the candidate's underlying REAL-WORLD FACT against the ALREADY COVERED list. Fail ONLY if the candidate explains the same concrete fact or mechanism as an existing entry — a reader who already read the covered entry would think "wait, this is the same thing again," not just "this reminds me of that."

Do NOT fail for sharing a narrative *pattern* or psychological *shape* with a covered entry. "An unfinished task nags at you" (Zeigarnik) and "a song loop nags at you" (earworms) and "a pressure difference nags at your ear until it resolves" are three DIFFERENT facts that happen to share the shape "unresolved state seeks resolution" — that shape is the whole genre of this account, not a reason to reject. Likewise two different body reflexes explained by two different nerve mechanisms are not duplicates just because both are "brain misreads a signal." Ask specifically: is this the same fact in a costume, or a genuinely different fact that merely rhymes structurally with one already told? Only the former fails.

Return ONLY a JSON object, no other text, no markdown fences:

{
  "universal_door_ok": <true|false>,
  "door_notes": "<why it fails, or empty string>",
  "plausibility_ok": <true|false>,
  "plausibility_notes": "<why it fails, or empty string>",
  "novelty_ok": <true|false>,
  "novelty_notes": "<which covered entry it overlaps with, or empty string>",
  "fix": "<one concrete sentence of direction if regenerating>"
}"""


def topic_gate_check(candidate: dict, digest: list[dict]) -> tuple[bool, list[str], dict]:
    user_turn = (
        f"ALREADY COVERED\n{_digest_block(digest)}\n\n"
        f"CANDIDATE\n"
        f"category: {candidate.get('category')}\n"
        f"prompt: {candidate.get('prompt')}\n"
        f"universal_door: {candidate.get('universal_door')}\n"
        f"dinner_table_line: {candidate.get('dinner_table_line')}\n\n"
        "Check it."
    )

    resp = _client.messages.create(
        model=config.CRITIC_MODEL,
        max_tokens=500,
        thinking={"type": "disabled"},
        system=_TOPIC_CRITIC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_turn}],
    )
    scores = _parse_json_response(extract_text(resp))

    reasons = []
    if scores.get("universal_door_ok") is not True:
        reasons.append(f"door: {scores.get('door_notes') or 'not affirmed'}")
    if scores.get("plausibility_ok") is not True:
        reasons.append(f"plausibility: {scores.get('plausibility_notes') or 'not affirmed'}")
    if scores.get("novelty_ok") is not True:
        reasons.append(f"novelty: {scores.get('novelty_notes') or 'not affirmed'}")

    # Schema completeness -- mechanical, not the gate model's job to judge.
    required = ("id", "category", "prompt", "universal_door", "hook_seed", "dinner_table_line", "emotion", "image_type")
    for field in required:
        if not candidate.get(field):
            reasons.append(f"missing required field '{field}'")
    if candidate.get("category") not in CATEGORIES:
        reasons.append(f"invalid category {candidate.get('category')!r}")
    if candidate.get("emotion") not in EMOTIONS:
        reasons.append(f"invalid emotion {candidate.get('emotion')!r}")
    if candidate.get("image_type") == "photo" and not (candidate.get("photo_keywords") and candidate.get("photo_subject")):
        reasons.append("photo topic missing photo_keywords/photo_subject")
    elif candidate.get("image_type") not in ("diagram", "photo"):
        reasons.append(f"invalid image_type {candidate.get('image_type')!r}")

    return (len(reasons) == 0, reasons, scores)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def get_dynamic_topic(recent_history: list[dict]) -> dict | None:
    """Tries live generation up to MAX_TOPIC_ATTEMPTS times. Returns the
    accepted topic dict, or None if nothing passed the gate -- there is no
    fallback bank. The caller must treat None as a skipped slot, exactly
    like any other validation failure in this pipeline."""
    digest = build_recent_topics_digest()
    last_category = recent_history[0]["category"] if recent_history else None

    # Accumulate EVERY rejection this run, not just the latest -- carrying
    # only the last failure forward let the model forget its own earlier
    # attempts and re-propose the identical idea two attempts later (observed
    # in testing: "feet swell on flights" proposed on both attempt 1 and 3).
    rejected_summaries: list[str] = []

    for attempt in range(1, MAX_TOPIC_ATTEMPTS + 1):
        retry_hint = ""
        if rejected_summaries:
            retry_hint = (
                "\n\nAlready tried and rejected this run -- do not repropose these ideas "
                "or close variants of them:\n" + "\n".join(rejected_summaries)
            )

        try:
            candidate = generate_candidate(digest, last_category, retry_hint)
            passed, reasons, scores = topic_gate_check(candidate, digest)
        except Exception as e:
            logger.warning("Topic generation attempt %d/%d errored: %s", attempt, MAX_TOPIC_ATTEMPTS, e)
            continue

        if passed:
            logger.info("Dynamic topic accepted: '%s' (category=%s)", candidate["id"], candidate["category"])
            return candidate

        logger.info("Topic candidate '%s' rejected: %s", candidate.get("id"), reasons)
        fix = scores.get("fix", "")
        summary = f"- \"{candidate.get('prompt', candidate.get('id'))}\" -- rejected: {'; '.join(reasons)}"
        if fix:
            summary += f" ({fix})"
        rejected_summaries.append(summary)

    logger.warning("Dynamic topic generation exhausted %d attempts -- no fallback, slot will be skipped.", MAX_TOPIC_ATTEMPTS)
    return None
