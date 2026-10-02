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
    """Parse the first complete JSON object in a model reply, ignoring any
    prose or a second object after it (models occasionally add one)."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = cleaned.find("{")
    if start < 0:
        raise json.JSONDecodeError("no JSON object found", cleaned, 0)
    obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    return obj


def overused_subjects(full_history: list[dict], top: int = 14) -> str:
    """The subject words that show up most across everything ever posted,
    computed from the history itself (not a fixed list). Telling the model
    where it has already gone heavily is what pushes it into new territory --
    left alone it keeps returning to the same few everyday subjects (feet,
    bread, ketchup...), which is where most of its rejected candidates came
    from."""
    from collections import Counter

    counts: Counter = Counter()
    for h in full_history:
        counts.update(_content_words(h["id"].replace("_", " ")))
    common = [(w, n) for w, n in counts.most_common(top) if n >= 2]
    return ", ".join(f"{w} ({n})" for w, n in common)


def choose_target_category(recent_history: list[dict]) -> str:
    """The category used least recently (never-used first), ties broken at
    random, never the immediately preceding one. Forcing the category spreads
    topics across all seven areas instead of letting the model gravitate to
    whichever it likes."""
    import random

    last_seen: dict[str, int] = {}
    for i, h in enumerate(recent_history):
        cat = h.get("category")
        if cat in CATEGORIES and cat not in last_seen:
            last_seen[cat] = i
    immediately_previous = recent_history[0].get("category") if recent_history else None
    pool = [c for c in CATEGORIES if c != immediately_previous] or list(CATEGORIES)
    oldest = max(last_seen.get(c, len(recent_history) + 1) for c in pool)
    return random.choice([c for c in pool if last_seen.get(c, len(recent_history) + 1) == oldest])


def generate_candidate(digest: list[dict], last_category: str | None, retry_hint: str = "",
                       target_category: str | None = None, saturated: str = "") -> dict:
    category_line = (
        f"\n\nThe category for this topic MUST be \"{target_category}\"."
        if target_category else
        (f"\n\nDo not use category \"{last_category}\" -- that was the immediately preceding post's category." if last_category else "")
    )
    saturated_line = (
        f"\n\nSUBJECTS ALREADY OVER-COVERED (the account has gone heavy on these; stay clear of them and explore genuinely different everyday territory): {saturated}"
        if saturated else ""
    )
    user_turn = (
        f"ALREADY COVERED (do not repeat the underlying idea of any of these)\n"
        f"{_digest_block(digest)}"
        f"{saturated_line}{category_line}{retry_hint}\n\n"
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

Check two things and be harsh:

# 1. GENUINE UNIVERSAL DOOR
Has essentially every human -- any age, any education, any country, possibly reading in a second language -- personally lived the `universal_door` experience? Not "could understand it" -- lived it. If the door requires domain membership, a specific culture, or specialist context, fail this.

# 2. FACTUAL PLAUSIBILITY
Is the `prompt` a genuinely well-established, plausible fact or mechanism -- not an invented statistic, a coin-flip claim, or something that sounds plausible but isn't actually verified common knowledge? If you're not confident it's true, fail this and say why.

Uniqueness is NOT your job: a separate all-time duplicate check runs after you and is the single authority on repeats. Judge only the two things above.

Return ONLY a JSON object, no other text, no markdown fences:

{
  "universal_door_ok": <true|false>,
  "door_notes": "<why it fails, or empty string>",
  "plausibility_ok": <true|false>,
  "plausibility_notes": "<why it fails, or empty string>",
  "fix": "<one concrete sentence of direction if regenerating>"
}"""


def topic_gate_check(candidate: dict) -> tuple[bool, list[str], dict]:
    user_turn = (
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
# Duplicate gate: ALL-TIME history, code first, then a focused pairwise check
# --------------------------------------------------------------------------
# The gate above asks a model to scan the last DIGEST_LIMIT topics and decide
# "is this substantially the same idea as any of these?". That is leaky: it let
# gen_why_ketchup_wont_pour through after ketchup_wont_pour, gen_microwave_cold_
# spots after microwave_uneven, and gen_why_bread_dries_stale after
# bread_stales_fridge -- real duplicates, all posted. And a recent-N window
# forgets anything older by construction. So uniqueness is enforced here
# against EVERYTHING ever posted:
#   1. retrieve the closest past topics by word overlap (any age)
#   2. a hard block in code for clear overlaps, independent of any model
#   3. a focused pairwise question to the model about only those closest few,
#      which is far more reliable than scanning an 80-entry list

_STOP = set(
    "a an the of to in on at for and or but is are was were be been it its this that these those with as by "
    "from into than then so such not no can could will would should may might must do does did done have has "
    "had having you your yours they their them we our us i me my he she his her who whom which what when "
    "where why how all any each both few more most other some own same just also only very much many one "
    "two three out up down off over under again once here there about between through during before after "
    "above below because while until if else too".split()
)
_GENERIC = set(
    "people person thing things way time lot often usually actually really feel feels feeling makes make "
    "made get gets getting got go goes going come comes back first part gen effect bias reason reasons "
    "explain explains explained phenomenon mechanism cause caused called known".split()
)

# Hard blocks must rest on real evidence. An overlap coefficient on a 1-2 word
# set is meaningless (an id-only description sharing one word scores 0.5), so
# the description rule demands sizeable descriptions AND many shared words;
# everything between "clearly the same" and "clearly different" goes to the
# pairwise model check instead.
HARD_DESC_OVERLAP = 0.55
HARD_DESC_MIN_WORDS = 6      # both descriptions must have at least this many content words
HARD_DESC_MIN_SHARED = 5
HARD_ID_OVERLAP = 0.99      # id words fully contained in the other id (with >= 2 shared words)
PAIRWISE_CANDIDATES = 8


def _stem(w: str) -> str:
    for suf in ("ing", "edly", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _content_words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOP and w not in _GENERIC and len(w) > 2}


def _overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def build_full_history() -> list[dict]:
    """Every distinct everyday topic ever attempted, of any age. Records with
    no stored description (old pre-migration topics) are represented by the
    words in their id, which still carries the subject."""
    import state

    entries: list[dict] = []
    seen: set[str] = set()
    for h in state.get_recent_history(limit=20000):
        if h.get("format") == "idiom":
            continue
        tid = h.get("topic_id")
        if not tid or tid in seen:
            continue
        seen.add(tid)
        entries.append({"id": tid, "description": h.get("topic_prompt") or tid.replace("gen_", "").replace("_", " ")})
    return entries


def _closest_past(candidate: dict, history: list[dict], k: int) -> list[dict]:
    cand_desc = _content_words(f"{candidate.get('prompt', '')} {candidate.get('universal_door', '')}")
    cand_id = _content_words(candidate.get("id", "").replace("_", " "))
    scored = []
    for h in history:
        past_desc = _content_words(h["description"])
        past_id = _content_words(h["id"].replace("_", " "))
        scored.append({
            "past": h,
            "desc_overlap": _overlap(cand_desc, past_desc),
            "desc_shared": len(cand_desc & past_desc),
            "desc_sizes": (len(cand_desc), len(past_desc)),
            "id_overlap": _overlap(cand_id, past_id),
            "id_shared": len(cand_id & past_id),
        })
    scored.sort(key=lambda r: r["desc_overlap"] + r["id_overlap"], reverse=True)
    return scored[:k]


_PAIRWISE_SYSTEM = """You compare ONE candidate topic for an everyday-mystery X account against a short list of topics the account has ALREADY posted, and decide which listed topics are a REPEAT of the candidate.

First, for the candidate and for each listed topic, state in under 8 words the specific everyday thing or question it explains (its "subject").

Two topics are a REPEAT only if their subjects are the same everyday thing, so that a reader of the earlier post would think "I've already read this". A different angle, wording, entry point or minor detail on the SAME subject is still a repeat.
  REPEAT: "why feet fall asleep" and "why feet fall asleep -- the tingling pattern".
  REPEAT: "microwaves heat food unevenly" and "why microwaves leave cold spots".
  REPEAT: "bread goes stale in the fridge" and "why bread dries out and goes stale".
Topics that merely share a general principle, theme, mechanism family or field are NOT repeats, however similar the explanation:
  NOT: "why airplane windows are round" vs "why manhole covers are round".
  NOT: "why cutting onions makes you cry" vs "why cut apples turn brown".
  NOT: "why feet fall asleep" vs "why feet hurt in the cold".
  NOT: "a casino hides clocks" vs "cabin lights dim at takeoff".

Return ONLY a JSON object, no other text:
{"candidate_subject": "...", "listed_subjects": ["1: ...", "2: ..."], "same_as": [<numbers of listed topics that are REPEATS; empty list if none>], "why": "<one short sentence>"}"""


def find_duplicate(candidate: dict, history: list[dict]) -> tuple[str, str] | None:
    """Returns (past_topic_id, reason) if the candidate repeats anything ever
    posted, else None."""
    closest = _closest_past(candidate, history, PAIRWISE_CANDIDATES)

    for c in closest:
        past = c["past"]
        sizes_ok = min(c["desc_sizes"]) >= HARD_DESC_MIN_WORDS
        if sizes_ok and c["desc_shared"] >= HARD_DESC_MIN_SHARED and c["desc_overlap"] >= HARD_DESC_OVERLAP:
            return past["id"], f"description word overlap {c['desc_overlap']:.2f} ({c['desc_shared']} shared words) with '{past['id']}'"
        if c["id_overlap"] >= HARD_ID_OVERLAP and c["id_shared"] >= 2:
            return past["id"], f"topic id overlaps '{past['id']}' ({c['id_shared']} shared subject words)"

    if not closest:
        return None
    listing = "\n".join(f"{i}. {c['past']['description']}" for i, c in enumerate(closest, 1))
    resp = _client.messages.create(
        model=config.CRITIC_MODEL,
        max_tokens=700,
        thinking={"type": "disabled"},
        system=_PAIRWISE_SYSTEM,
        messages=[{"role": "user", "content": f"CANDIDATE: {candidate.get('prompt')}\n\nALREADY POSTED:\n{listing}"}],
    )
    verdict = _parse_json_response(extract_text(resp))
    same = [i for i in verdict.get("same_as", []) if isinstance(i, int) and 1 <= i <= len(closest)]
    if same:
        past = closest[same[0] - 1]["past"]
        return past["id"], f"model judged it a repeat of '{past['id']}': {verdict.get('why', '')}"
    return None


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def get_dynamic_topic(recent_history: list[dict]) -> dict | None:
    """Tries live generation up to MAX_TOPIC_ATTEMPTS times. Returns the
    accepted topic dict, or None if nothing passed the gate -- there is no
    fallback bank. The caller must treat None as a skipped slot, exactly
    like any other validation failure in this pipeline."""
    digest = build_recent_topics_digest()
    full_history = build_full_history()
    target_category = choose_target_category(recent_history)
    saturated = overused_subjects(full_history)
    # .get(), not recent_history[0]["category"] -- the most recent record can
    # be a well-formed-but-sparse skip (e.g. "topic generation exhausted",
    # which has no topic/category at all) and this line ran on every single
    # invocation, so a bare subscript here turned one such record into a
    # 5-day, self-perpetuating outage (2026-09-11 to 2026-09-15) affecting
    # both formats at once.
    last_category = recent_history[0].get("category") if recent_history else None

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
            candidate = generate_candidate(digest, last_category, retry_hint, target_category, saturated)
            passed, reasons, scores = topic_gate_check(candidate)
        except Exception as e:
            logger.warning("Topic generation attempt %d/%d errored: %s", attempt, MAX_TOPIC_ATTEMPTS, e)
            continue

        if passed:
            try:
                dup = find_duplicate(candidate, full_history)
            except Exception as e:  # noqa: BLE001
                # Fail closed: if uniqueness cannot be established, do not accept.
                logger.warning("Duplicate check errored for '%s': %s", candidate.get("id"), e)
                dup = (candidate.get("id", "?"), f"duplicate check errored: {e}")
            if dup is None:
                logger.info("Dynamic topic accepted: '%s' (category=%s)", candidate["id"], candidate["category"])
                return candidate
            passed, reasons, scores = False, [f"duplicate: {dup[1]}"], {"fix": "Pick a clearly different subject, not a new angle on the same phenomenon."}

        logger.info("Topic candidate '%s' rejected: %s", candidate.get("id"), reasons)
        fix = scores.get("fix", "")
        summary = f"- \"{candidate.get('prompt', candidate.get('id'))}\" -- rejected: {'; '.join(reasons)}"
        if fix:
            summary += f" ({fix})"
        rejected_summaries.append(summary)

    logger.warning("Dynamic topic generation exhausted %d attempts -- no fallback, slot will be skipped.", MAX_TOPIC_ATTEMPTS)
    return None
