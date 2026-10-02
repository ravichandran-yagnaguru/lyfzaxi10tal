"""
Researches NEW idioms so the idiom format never has to repeat one.

WHY THIS EXISTS
---------------
idiom_topics.py is a hand-researched bank of 30. At 2 posts/day that is a
15-day supply, and once it ran out (2026-09-28) the picker's "recycle the
least recently posted" fallback began re-posting idioms (white elephant,
steal thunder, rule of thumb, saved by the bell). That fallback contradicted
the standing "100% no repeated post" rule, and nobody flagged it when it was
built. There is no way to hand-research an unbounded supply, so new idioms
are researched automatically -- but idiom accuracy is this format's whole
credibility bet (the pilot found 2 of 5 popular origins needed correction),
so research is held to a stricter standard than anything else here:

  1. propose_idiom()  -- Claude proposes ONE famous idiom, shown everything
                         already covered so it can't re-propose.
  2. research_idiom() -- Claude WITH WEB SEARCH builds a full bank entry:
                         documented origin, the popular myth if any, and an
                         honest confidence tier (solid / contested / folklore).
  3. audit_idiom()    -- a SECOND, independent Claude+web-search pass that
                         sees only the claim, not the researcher's reasoning,
                         and re-verifies it from scratch. Disagreement on the
                         facts rejects the entry; disagreement on the tier
                         resolves to the MORE conservative one.
  4. structural checks + a code-level duplicate gate.

Entries that pass are stored in Firestore's `idiom_queue` collection (status
"ready"); the posting path only ever reads from there, so slow, costly
research never sits on the critical path of a scheduled post. Rejected
candidates are stored too (status "rejected") so they are never re-proposed.
The existing draft generator/critic then treat a queue entry exactly like a
hand-written bank entry.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import anthropic

import config
import idiom_topics
import state
from llm_utils import extract_text

logger = logging.getLogger("concept-bot")

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)

# The basic (non-code-executing) search tool, deliberately: the newer
# dynamic-filtering variant took ~270s per idiom (research + audit) in
# testing versus ~26s here, with the same quality of result.
_WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}

VALID_TIERS = ("solid", "contested", "folklore")
_TIER_RANK = {"solid": 0, "contested": 1, "folklore": 2}  # higher = more conservative

# Queue depth the refill job tries to maintain, and how many idioms a single
# refill request may research (each takes roughly 1-2 minutes).
TARGET_QUEUE_DEPTH = 8
MAX_NEW_PER_REFILL = 3
MAX_PROPOSALS_PER_NEW_IDIOM = 4

# An idiom whose draft fails the quality gate this many times is given up on
# rather than retried forever.
MAX_ATTEMPTS_PER_IDIOM = 2


# --------------------------------------------------------------------------
# Duplicate gate (code-level, independent of any model's say-so)
# --------------------------------------------------------------------------

_PLACEHOLDER_WORDS = {"someone", "someones", "ones", "one", "my", "your", "his", "her", "their", "our", "its", "somebody", "somebodys"}
_DROP_WORDS = {"a", "an", "the", "to"}


def _tokens(phrase: str) -> list[str]:
    words = re.sub(r"[^a-z' ]", " ", phrase.lower().replace("-", " ")).split()
    out: list[str] = []
    for w in words:
        w = w.replace("'s", "s").replace("'", "")
        if w in _DROP_WORDS:
            continue
        if w in _PLACEHOLDER_WORDS:
            out.append("_")
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(w) > 4 and w.endswith(suffix):
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


def _contains(longer: list[str], shorter: list[str]) -> bool:
    n = len(shorter)
    return n > 0 and any(longer[i:i + n] == shorter for i in range(len(longer) - n + 1))


def is_duplicate(phrase: str, covered_phrases: list[str]) -> str | None:
    """Returns the covered phrase this one duplicates, or None. Tolerates the
    usual variants: articles, someone's/my/your, tense and plurals, and one
    phrase simply being a longer form of the other."""
    cand = [t for t in _tokens(phrase) if t != "_"]
    if not cand:
        return None
    for other in covered_phrases:
        existing = [t for t in _tokens(other) if t != "_"]
        if not existing:
            continue
        if cand == existing:
            return other
        if min(len(cand), len(existing)) >= 2 and (_contains(cand, existing) or _contains(existing, cand)):
            return other
    return None


def covered_phrases() -> list[str]:
    """Every idiom ever banked, queued (any status), or posted."""
    phrases = [t["idiom"] for t in idiom_topics.IDIOM_TOPICS]
    phrases += [q["idiom"] for q in state.queue_all() if q.get("idiom")]
    phrases += [h["idiom_phrase"] for h in state.get_idiom_history() if h.get("idiom_phrase")]
    seen: set[str] = set()
    unique = []
    for p in phrases:
        if p.lower() not in seen:
            seen.add(p.lower())
            unique.append(p)
    return unique


# --------------------------------------------------------------------------
# JSON helper
# --------------------------------------------------------------------------

def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


# --------------------------------------------------------------------------
# Step 1: propose
# --------------------------------------------------------------------------

_PROPOSE_SYSTEM = """You pick ONE idiom for an X account that tells where famous English idioms come from. Readers are ordinary people worldwide, many reading English as a second language.

Pick an idiom that:
- nearly every English speaker has heard and that is still used in everyday speech today
- is made of simple, concrete words (a reader can picture something)
- has some interesting origin story OR a famously unknown origin (both are fine)

Never pick an idiom that is vulgar, a slur or built on one, tied to a real tragedy or atrocity, political, religious, or whose popular origin story is about mistreating a group of people.

You will be given the list of idioms already covered. Do not pick any of them, any variant of them (different tense, "someone's" vs "my", with or without "a/the"), or any of the idioms rejected earlier in this run.

Return ONLY a JSON object, no other text: {"idiom": "<the phrase in its most common form>"}"""


def propose_idiom(covered: list[str], rejected_this_run: list[str]) -> str:
    covered_block = "\n".join(f"- {p}" for p in covered) or "(none)"
    rejected_block = ("\n\nRejected earlier in this run (do not pick):\n" + "\n".join(f"- {p}" for p in rejected_this_run)) if rejected_this_run else ""
    resp = _client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=200,
        thinking={"type": "disabled"},
        system=_PROPOSE_SYSTEM,
        messages=[{"role": "user", "content": f"ALREADY COVERED:\n{covered_block}{rejected_block}\n\nPick one new idiom."}],
    )
    return _parse_json(extract_text(resp))["idiom"].strip()


# --------------------------------------------------------------------------
# Step 2: research (web search)
# --------------------------------------------------------------------------

_RESEARCH_SYSTEM = """You research the TRUE origin of one English idiom, using web search, and produce one entry for a fact-checked idiom bank. Accuracy is everything: popular idiom folklore is unreliable, and in earlier testing a large share of widely repeated origin stories turned out to be wrong or unprovable.

# How to research
- Search for the idiom's etymology and read what authoritative sources say. Consult at least TWO independent reputable sources: major dictionaries and etymology references (Oxford English Dictionary summaries, Merriam-Webster, Etymonline, Wiktionary with dated citations), word-historian sites (World Wide Words, Phrases.org.uk, Wordorigins.org), Library of Congress, Snopes, university or museum pages. Do NOT rely on listicle/content-farm sites or forums (theidioms.com, Quora, Reddit, "Reader's Digest", etc.) for any fact.
- Establish the earliest documented use if sources give one (year plus author or work).
- Note the popular origin story people repeat, and whether sources support it.

# Confidence tier -- be honest, never inflate
- "solid": reputable sources agree on the origin and it is documented.
- "contested": there is real documentary evidence, but the link from the evidence to the idiom is unproven or the sources disagree.
- "folklore": the real origin is unknown; the famous story is a legend with no good documentation. (This is fine -- we tell it honestly as a passed-down story.)

# What to output (a single JSON object, nothing else)
{
  "idiom": "<canonical phrase>",
  "verified_origin": "<1-3 sentences. ONLY facts your sources actually state: earliest documented use with year and source, and what historians conclude. For folklore, say plainly what IS documented (e.g. first appearance in print) and that the origin is unknown. Do not invent names, dates, places or numbers.>",
  "popular_myth": "<the widely repeated story the sources do NOT support, in one or two sentences, or null if there isn't one>",
  "confidence": "solid" | "contested" | "folklore",
  "story": "<3-5 plain sentences setting the origin scene a reader could picture. Solid: faithful to the documented facts. Contested: the best-supported scene, hedged. Folklore: the legend, explicitly framed as 'the story people tell'. Concrete people, objects, actions. No invented checkable specifics beyond verified_origin.>",
  "reveal": "<the idiom phrase>",
  "use": "<one or two sentences describing a concrete modern moment where someone would say it>",
  "image_style": "<ONE sentence describing a drawable engraving scene: the setting, the people, the action, period-appropriate. No text or lettering in the picture. No real named living person.>",
  "era": "<century of the depicted scene as '15th', '16th', ... '19th'. If the scene is 20th century or later, use '19th'.>",
  "sources": ["<url you actually consulted>", "..."]
}

Return ONLY the JSON object."""


def research_idiom(idiom: str) -> dict:
    resp = _client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=3000,
        thinking={"type": "disabled"},
        system=_RESEARCH_SYSTEM,
        tools=[_WEB_SEARCH_TOOL],
        messages=[{"role": "user", "content": f"Research this idiom and produce the entry: {idiom}"}],
    )
    return _parse_json(extract_text(resp))


# --------------------------------------------------------------------------
# Step 3: independent audit (a second, separate web-search pass)
# --------------------------------------------------------------------------

_AUDIT_SYSTEM = """You are an independent fact-checker for an idiom-origin bank. Another researcher produced the entry you are shown. You have NOT seen their reasoning and must not trust it: verify the claims yourself from scratch using web search, consulting reputable etymology sources (major dictionaries, Etymonline, World Wide Words, Phrases.org.uk, Wordorigins.org, Library of Congress, Snopes). Do NOT rely on listicle/content-farm sites or forums.

Check:
1. Is `verified_origin` accurate -- does every factual claim (dates, names, works, conclusions) match what reputable sources say? Any claim you cannot confirm, or that sources contradict, makes it inaccurate.
2. Is `popular_myth` (if given) really a widely repeated story that sources do not support?
3. Is the `confidence` tier honest? "solid" only if reputable sources agree on a documented origin; "contested" if there is documentary evidence but an unproven link or sources disagree; "folklore" if the real origin is unknown and the famous story is legend.
4. Does `story` stay faithful to verified_origin (for folklore, is it clearly framed as legend)?

Return ONLY a JSON object, no other text:
{
  "origin_accurate": true | false,
  "myth_ok": true | false,
  "story_faithful": true | false,
  "suggested_tier": "solid" | "contested" | "folklore",
  "notes": "<one or two sentences: what you found, and exactly which claim is wrong if any>"
}"""


def audit_idiom(entry: dict) -> dict:
    claim = {k: entry.get(k) for k in ("idiom", "verified_origin", "popular_myth", "confidence", "story")}
    resp = _client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=1500,
        thinking={"type": "disabled"},
        system=_AUDIT_SYSTEM,
        tools=[_WEB_SEARCH_TOOL],
        messages=[{"role": "user", "content": "Verify this entry:\n\n" + json.dumps(claim, indent=2)}],
    )
    return _parse_json(extract_text(resp))


# --------------------------------------------------------------------------
# Step 4: structural checks and assembly
# --------------------------------------------------------------------------

_REQUIRED = ("idiom", "verified_origin", "confidence", "story", "reveal", "use", "image_style", "era")


def _slug(phrase: str) -> str:
    return "idiom_" + re.sub(r"[^a-z0-9]+", "_", phrase.lower()).strip("_")[:50]


def structural_problems(entry: dict) -> list[str]:
    problems = [f"missing '{f}'" for f in _REQUIRED if not entry.get(f)]
    if entry.get("confidence") not in VALID_TIERS:
        problems.append(f"invalid confidence {entry.get('confidence')!r}")
    if not re.fullmatch(r"\d{2}th", str(entry.get("era", ""))):
        problems.append(f"era {entry.get('era')!r} is not like '18th'")
    if not entry.get("sources"):
        problems.append("no sources listed")
    return problems


def research_and_vet(idiom: str) -> tuple[dict | None, str]:
    """Runs research + independent audit for one proposed idiom. Returns
    (entry, "") when it passes, or (None, reason) when it doesn't."""
    entry = research_idiom(idiom)
    problems = structural_problems(entry)
    if problems:
        return None, "structural: " + "; ".join(problems)

    audit = audit_idiom(entry)
    if audit.get("origin_accurate") is not True:
        return None, f"audit: origin not confirmed -- {audit.get('notes', '')}"
    if audit.get("story_faithful") is not True:
        return None, f"audit: story not faithful -- {audit.get('notes', '')}"
    if entry.get("popular_myth") and audit.get("myth_ok") is not True:
        return None, f"audit: myth claim not confirmed -- {audit.get('notes', '')}"

    # Tiers: disagreement resolves to the MORE conservative one, never upward.
    auditor_tier = audit.get("suggested_tier")
    if auditor_tier in _TIER_RANK and _TIER_RANK[auditor_tier] > _TIER_RANK[entry["confidence"]]:
        logger.info("Audit downgraded '%s' from %s to %s", idiom, entry["confidence"], auditor_tier)
        entry["confidence"] = auditor_tier

    entry["audit_notes"] = audit.get("notes", "")
    return entry, ""


# --------------------------------------------------------------------------
# Queue refill
# --------------------------------------------------------------------------

def available_in_queue(queue: list[dict], idiom_history: list[dict]) -> list[dict]:
    """Queue entries that are ready and not yet posted or given up on."""
    posted = {h.get("topic_id") for h in idiom_history if h.get("status") == "posted"}
    skips: dict[str, int] = {}
    for h in idiom_history:
        if h.get("status") == "skipped" and h.get("topic_id"):
            skips[h["topic_id"]] = skips.get(h["topic_id"], 0) + 1
    return [
        q for q in queue
        if q.get("status") == "ready" and q["id"] not in posted and skips.get(q["id"], 0) < MAX_ATTEMPTS_PER_IDIOM
    ]



def refill_queue(target_depth: int = TARGET_QUEUE_DEPTH, max_new: int = MAX_NEW_PER_REFILL, time_budget_s: float = 200.0) -> dict:
    """Researches new idioms until the ready queue reaches target_depth, up to
    max_new accepted entries, within a wall-clock budget. Returns a summary."""
    started = time.monotonic()
    queue = state.queue_all()
    history = state.get_idiom_history()
    depth = len(available_in_queue(queue, history))
    summary = {"depth_before": depth, "accepted": [], "rejected": []}

    if depth >= target_depth:
        summary["note"] = "queue already at target depth; nothing to do"
        summary["depth_after"] = depth
        return summary

    covered = covered_phrases()
    rejected_this_run: list[str] = []

    while len(summary["accepted"]) < max_new and depth + len(summary["accepted"]) < target_depth:
        accepted_one = False
        for _ in range(MAX_PROPOSALS_PER_NEW_IDIOM):
            if time.monotonic() - started > time_budget_s:
                summary["note"] = "time budget reached"
                summary["depth_after"] = depth + len(summary["accepted"])
                return summary

            try:
                phrase = propose_idiom(covered, rejected_this_run)
            except Exception as e:  # noqa: BLE001
                logger.warning("Idiom proposal failed: %s", e)
                continue

            duplicate_of = is_duplicate(phrase, covered)
            if duplicate_of:
                logger.info("Proposed '%s' duplicates '%s'; re-proposing", phrase, duplicate_of)
                rejected_this_run.append(phrase)
                continue

            try:
                entry, reason = research_and_vet(phrase)
            except Exception as e:  # noqa: BLE001
                logger.warning("Research of '%s' errored: %s", phrase, e)
                rejected_this_run.append(phrase)
                continue

            covered.append(phrase)
            if entry is None:
                logger.info("Idiom '%s' rejected: %s", phrase, reason)
                rejected_this_run.append(phrase)
                state.queue_put({"id": _slug(phrase), "idiom": phrase, "status": "rejected", "reject_reason": reason})
                summary["rejected"].append({"idiom": phrase, "reason": reason})
                continue

            entry["id"] = _slug(entry["idiom"])
            entry["status"] = "ready"
            entry["source_kind"] = "researched"
            state.queue_put(entry)
            logger.info("Idiom '%s' accepted into queue (%s)", entry["idiom"], entry["confidence"])
            summary["accepted"].append({"idiom": entry["idiom"], "confidence": entry["confidence"]})
            covered.append(entry["idiom"])
            accepted_one = True
            break

        if not accepted_one:
            summary["note"] = "no proposal survived vetting this run"
            break

    summary["depth_after"] = depth + len(summary["accepted"])
    return summary
