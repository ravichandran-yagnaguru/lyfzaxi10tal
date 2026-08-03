"""
concept-bot project reviewer — mechanical layer.

DESIGN PRINCIPLE
----------------
Never ask a language model to do what a regex can do. The critic-calibration
run proved this the hard way: Haiku was told "a first line over fifteen words
caps fluency at 5", was handed a 30-word opening, and scored it 9. Countable
things get counted in code; judgment goes to the LLM reviewer (see REVIEWER.md).

This script encodes checks that are specific to THIS project — the coupling
between config values and the topic bank, the invariants the pipeline relies
on, the failure modes already seen in production. Generic linting is ruff's
job, not this file's.

USAGE
-----
    python review.py              # full report
    python review.py --fail-on high   # exit 1 if any HIGH finding (for CI)
    python review.py --json out.json

Runs entirely offline. No API calls, no network, no credentials needed.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, asdict

REPO = os.path.dirname(os.path.abspath(__file__))

SEV_ORDER = {"high": 3, "medium": 2, "low": 1, "info": 0}


@dataclass
class Finding:
    severity: str      # high | medium | low | info
    area: str          # correctness | cost | resilience | content | ops
    where: str
    what: str
    why: str
    fix: str


findings: list[Finding] = []


def add(severity, area, where, what, why, fix):
    findings.append(Finding(severity, area, where, what, why, fix))


def read(name: str) -> str | None:
    path = os.path.join(REPO, name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def const(src: str, name: str):
    """Pull a module-level int/str constant out of source without importing it."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    try:
                        return ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        return None
    return None


# ==========================================================================
# 1. CORRECTNESS — invariants the pipeline silently depends on
# ==========================================================================

def check_history_window_vs_bank():
    """
    The single highest-value check in this file.

    pick_next_topic() computes `used_ids` from recent_history, and
    get_recent_history() is capped at RECENT_HISTORY_WINDOW. So the bot's
    memory of "have I posted this already" is only as deep as that window —
    NOT as deep as the bank. A 54-topic bank with a 7-entry window means the
    rotation can legitimately repeat a topic after 8 posts, which at 4
    posts/day is under two days.

    Followers notice repeats far faster than they notice anything else.
    """
    cfg = read("config.py")
    topics_src = read("topics.py")
    sched = read("schedule.yaml")
    if not (cfg and topics_src):
        return

    window = const(cfg, "RECENT_HISTORY_WINDOW")
    bank = topics_src.count('"id":')
    if not window or not bank:
        return

    posts_per_week = None
    if sched:
        posts_per_week = len(re.findall(r'"\d{2}:\d{2}"', sched))

    if window < bank:
        days = f" (~{window / (posts_per_week / 7):.1f} days at the current schedule)" if posts_per_week else ""
        add(
            "high", "correctness", "config.RECENT_HISTORY_WINDOW",
            f"Window is {window} but the bank has {bank} topics{days}.",
            "pick_next_topic() only sees the last "
            f"{window} posts, so a topic can legally repeat after {window + 1} posts "
            "even though the bank could go far longer without repeating. The "
            "cycle-reset logic that was designed to prevent this can't see far "
            "enough back to work.",
            f"Raise RECENT_HISTORY_WINDOW to at least {bank} (e.g. {bank * 2}) so the "
            "cycle logic can actually observe a full pass through the bank. Firestore "
            "reads are trivially cheap at this volume; there is no cost reason to keep "
            "it at 7.",
        )


def check_post_length_vs_platform():
    """
    generate_prompt asks for 120-260 words. That is roughly 660-1430
    characters. The standard X post limit is 280. Long posts require Premium.

    Posting currently works, which implies the account already has long-post
    capability — but nothing in the code asserts it, so a subscription lapse
    would turn into a silent stream of API errors at 9am.
    """
    gp = read("generate_prompt.py")
    poster = read("poster.py")
    if not gp:
        return

    m = re.search(r"(\d+)\s+to\s+(\d+)\s+words", gp)
    if not m:
        return
    lo, hi = int(m.group(1)), int(m.group(2))
    lo_chars, hi_chars = int(lo * 5.5), int(hi * 5.5)

    if hi_chars > 280:
        has_guard = bool(poster and re.search(r"280|len\(text\)|MAX_POST", poster))
        add(
            "medium" if not has_guard else "info", "resilience", "poster.post",
            f"Drafts target {lo}-{hi} words (~{lo_chars}-{hi_chars} chars) but the "
            "standard X limit is 280.",
            "Long posts depend on the account retaining Premium. If that lapses, or "
            "if credentials are ever swapped to a non-Premium account, every post "
            "fails at the API boundary rather than at validation — after paying for "
            "generation, critique and image sourcing.",
            "Add an explicit length assertion in poster.post() with a clear error "
            "message naming Premium as the likely cause, so the failure is "
            "self-diagnosing in the logs.",
        )


def check_image_failure_consumes_attempts():
    """
    In app.py the retry loop is `for attempt in range(1, MAX+1)`, and an
    image-sourcing failure hits `continue` — consuming one of the three
    generation attempts even though generation succeeded.

    Two photo failures leave a single generation attempt for a slot, so an
    unrelated Unsplash outage degrades content quality.
    """
    app_src = read("app.py")
    if not app_src or "ImageSourcingError" not in app_src:
        return
    if "image_attempts" in app_src or "attempts_used" in app_src:
        return
    add(
        "medium", "correctness", "app.run_pipeline",
        "Image-sourcing failures consume generation attempts.",
        "A successful, validated draft is discarded and counted against "
        "MAX_GENERATION_ATTEMPTS because its photo lookup failed. Two photo "
        "failures leave one attempt for the whole slot, so a transient Unsplash "
        "problem quietly lowers content quality rather than just changing topic.",
        "Track image retries in a separate counter from generation attempts, or "
        "re-source the image for a new topic without re-entering the generation "
        "loop. The validated draft is the expensive artifact — don't throw it away "
        "for an image problem.",
    )


def check_skip_record_shape():
    """
    record_post() on the skip path writes no opening_line, which is fine, but
    get_recent_history() returns skipped entries too and app.py builds
    recent_openings from them via .get(). Verify the guard exists.
    """
    app_src = read("app.py")
    if not app_src:
        return
    if 'h.get("opening_line")' not in app_src and 'h["opening_line"]' in app_src:
        add(
            "high", "correctness", "app.run_pipeline",
            "recent_openings indexes opening_line directly.",
            "Skipped entries are written without opening_line, so a KeyError will "
            "crash the pipeline on the first run after any skipped slot.",
            "Use .get() and filter falsy values.",
        )


# ==========================================================================
# 2. RESILIENCE — what happens when an external thing misbehaves
# ==========================================================================

def check_unguarded_downloads():
    """
    images.py wraps the SEARCH calls in try/except RequestException but not
    the subsequent image DOWNLOAD calls. A CDN hiccup mid-download raises
    straight out of source_image() as an unhandled RequestException, which is
    not ImageSourcingError, so app.py's handler misses it and the whole
    request 500s.
    """
    src = read("images.py")
    if not src:
        return
    lines = src.splitlines()
    for i, line in enumerate(lines, 1):
        if re.search(r"requests\.get\(.*\)\.content", line):
            window = "\n".join(lines[max(0, i - 12):i])
            # a download guarded by its own try is fine; look for one enclosing it
            if "try:" not in window.split("for photo")[-1]:
                add(
                    "high", "resilience", f"images.py:{i}",
                    "Image download is not wrapped in try/except.",
                    "Only the search call is guarded. A failure while fetching the "
                    "image bytes raises RequestException, which is not "
                    "ImageSourcingError, so app.py's except clause does not catch it "
                    "and the entire /post request returns 500 instead of degrading to "
                    "a skipped slot.",
                    "Wrap the download in try/except requests.exceptions.RequestException "
                    "and continue to the next candidate photo, matching how search "
                    "failures are already handled.",
                )
                break


def check_no_api_retry():
    """Anthropic calls have no backoff. A single 429/529 kills the slot."""
    for name in ("generate.py", "validate.py", "images.py"):
        src = read(name)
        if not src or "messages.create" not in src:
            continue
        if re.search(r"max_retries|backoff|retry|tenacity", src):
            continue
        add(
            "medium", "resilience", f"{name}",
            "Anthropic client is constructed without a retry policy.",
            "A single 429 or 529 on a scheduled slot burns an attempt with no "
            "backoff. The SDK supports this natively; not setting it means "
            "transient overload looks identical to a real failure.",
            "Construct the client with anthropic.Anthropic(api_key=..., max_retries=3). "
            "One-line change, applies to every call site.",
        )
        break


def check_media_cleanup():
    src = read("images.py")
    app_src = read("app.py")
    if not src:
        return
    if re.search(r"os\.remove|shutil\.rmtree|unlink|TemporaryDirectory", src + (app_src or "")):
        return
    add(
        "low", "ops", "images.MEDIA_DIR",
        "Downloaded images and rendered diagrams are never deleted.",
        "Cloud Run instances are ephemeral, so this rarely bites — but a "
        "long-lived warm instance accumulates files in the container's writable "
        "layer, which is memory-backed on Cloud Run and counts against the "
        "instance memory limit.",
        "Delete the file after poster.post() returns, or write into "
        "tempfile.TemporaryDirectory().",
    )


# ==========================================================================
# 3. CONTENT — the bank and the gate, which is where the product actually is
# ==========================================================================

def check_bank_health():
    src = read("topics.py")
    if not src:
        return

    cats = re.findall(r'"category":\s*"(\w+)"', src)
    if not cats:
        return
    from collections import Counter
    counts = Counter(cats)
    lo_cat, lo_n = counts.most_common()[-1]
    hi_cat, hi_n = counts.most_common()[0]

    if hi_n >= lo_n * 2:
        add(
            "low", "content", "topics.TOPICS",
            f"Category sizes are uneven: {hi_cat}={hi_n}, {lo_cat}={lo_n}.",
            "Rotation picks a category first, then a topic within it. Small "
            "categories therefore cycle through their topics much faster and repeat "
            "sooner than large ones — the imbalance compounds rather than averaging out.",
            "Even the categories out, or weight category selection by size so each "
            "topic has a roughly equal chance of being chosen.",
        )

    emotions = re.findall(r'"emotion":\s*"(\w+)"', src)
    if emotions:
        ec = Counter(emotions)
        rare = [e for e, n in ec.items() if n < len(emotions) / 12]
        if rare:
            add(
                "info", "content", "topics.TOPICS",
                f"Thin emotion coverage: {', '.join(sorted(rare))}.",
                "The emotion filter avoids repeating a flavour back to back. An "
                "emotion with very few topics will be filtered out often and rarely "
                "chosen, weakening the variable-reward effect it exists to create.",
                "Add topics in the thin emotions, or accept that the rotation is "
                "effectively three-flavoured.",
            )


def check_gate_mechanical_coverage():
    """
    The calibration run proved the LLM critic does not reliably apply its own
    countable rules. Any rule stated numerically in the critic prompt should
    ALSO exist as a deterministic check.
    """
    vp = read("validate_prompt.py")
    v = read("validate.py")
    if not (vp and v):
        return

    stated = re.findall(r"(?:over|under|more than|fewer than)\s+(\w+teen|\w+ty|\d+)\s+words", vp)
    if not stated:
        return

    has_opening_check = bool(re.search(r"first[_ ]?sentence|opening.*split|len\(.*split\(\)\)", v))
    if not has_opening_check:
        add(
            "high", "content", "validate.rule_based_checks",
            "The critic prompt states countable word limits that no code enforces.",
            "Calibration confirmed this fails in practice: a 30-word opening line "
            "scored 9 on fluency against a prompt that explicitly caps it at 5. An "
            "LLM asked to count will approximate; a regex will not.",
            "Move every numeric rule in CRITIC_SYSTEM_PROMPT into rule_based_checks() "
            "— opening-line word count, gift sentence length, gift verbatim presence "
            "in the draft. Leave the LLM only genuine judgment.",
        )

    if "dinner_table_sentence" in vp and "dinner_table_sentence" not in v:
        add(
            "high", "content", "validate.py",
            "The critic's extracted gift is never verified against the draft.",
            "REQUIRE_EXTRACTED_GIFT only checks the string is non-empty. Calibration "
            "showed the critic returning 40-word multi-sentence passages, and "
            "sometimes paraphrases, as 'the retellable sentence' — all scored 9.",
            "After critic_check, assert the gift is (a) under ~25 words, (b) a single "
            "sentence, (c) present verbatim in the draft after whitespace "
            "normalisation. Fail the draft otherwise.",
        )


# ==========================================================================
# 4. OPS
# ==========================================================================

def check_schedule_alignment():
    sched = read("schedule.yaml")
    if not sched:
        return
    tz = re.search(r'timezone:\s*"([^"]+)"', sched)
    slots = re.findall(r'"\d{2}:\d{2}"', sched)
    if tz and "Los_Angeles" in tz.group(1):
        add(
            "medium", "ops", "schedule.yaml",
            f"Schedule is anchored to {tz.group(1)}.",
            "The density of the English-language audience sits on US Eastern; peak "
            "windows are 8-10am, 12-2pm and 5-7pm ET. Pacific anchoring shifts every "
            "slot three hours off those windows.",
            "Re-anchor to America/New_York and re-run manage_schedule.py. Verify the "
            "job count stays at 3 to remain inside the Cloud Scheduler free tier.",
        )
    if len(slots) >= 28:
        add(
            "medium", "content", "schedule.yaml",
            f"{len(slots)} posts/week ({len(slots)//7}/day).",
            "Per-post engagement rate is what the ranking system scores. Posting "
            "volume above what the quality gate can sustain dilutes that ratio and "
            "trains the algorithm to show the account to fewer people. The strategy "
            "doc targets 2 originals/day plus replies.",
            "Cut to 2/day until the gate is calibrated and per-post engagement is "
            "measured. Volume is the last lever to pull, not the first.",
        )


def check_tests():
    has = any(
        n.startswith("test_") or n == "tests"
        for n in os.listdir(REPO)
    )
    if not has:
        add(
            "medium", "correctness", "repo",
            "No test files.",
            "pick_next_topic() has already produced one production incident "
            "(deterministic tie-break causing duplicate posts). Its behaviour is "
            "subtle, history-dependent, and now carries an added emotion filter — "
            "exactly the kind of logic that regresses silently.",
            "Add tests for: no category repeats back-to-back; no topic repeats within "
            "a full cycle; exclude_ids honoured; emotion filter never empties the "
            "candidate set; fresh-start selection spreads across topics over many "
            "trials. Pure functions, no mocking, no API calls.",
        )


def check_secrets_hygiene():
    for name in (".env", ".env.yaml"):
        if os.path.exists(os.path.join(REPO, name)):
            gi = read(".gitignore") or ""
            if name not in gi:
                add(
                    "high", "ops", name,
                    f"{name} exists but is not in .gitignore.",
                    "This repo's history was already force-rewritten once to purge "
                    "leaked live credentials. A second leak is avoidable.",
                    f"Add {name} to .gitignore immediately and confirm it is untracked "
                    "with `git ls-files | grep env`.",
                )


# ==========================================================================
# Report
# ==========================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description="Review the concept-bot project.")
    ap.add_argument("--fail-on", choices=["high", "medium", "low"], help="exit 1 at or above this severity")
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args()

    for fn in (
        check_history_window_vs_bank,
        check_post_length_vs_platform,
        check_image_failure_consumes_attempts,
        check_skip_record_shape,
        check_unguarded_downloads,
        check_no_api_retry,
        check_media_cleanup,
        check_bank_health,
        check_gate_mechanical_coverage,
        check_schedule_alignment,
        check_tests,
        check_secrets_hygiene,
    ):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — one broken check shouldn't hide the rest
            print(f"[reviewer error in {fn.__name__}: {e}]", file=sys.stderr)

    findings.sort(key=lambda f: -SEV_ORDER[f.severity])

    print("=" * 78)
    print("concept-bot — mechanical review")
    print("=" * 78)

    if not findings:
        print("\nNo findings. Run the judgment review in REVIEWER.md as well.")
        return 0

    from collections import Counter
    counts = Counter(f.severity for f in findings)
    print("  " + "   ".join(f"{s}: {counts.get(s, 0)}" for s in ("high", "medium", "low", "info")))

    current = None
    for f in findings:
        if f.severity != current:
            current = f.severity
            print(f"\n{'-' * 78}\n{f.severity.upper()}\n{'-' * 78}")
        print(f"\n[{f.area}] {f.where}")
        print(f"  {f.what}")
        print(f"  why:  {f.why}")
        print(f"  fix:  {f.fix}")

    print(f"\n{'=' * 78}")
    print("This layer only catches what is countable. For architecture, naming,")
    print("prompt quality and product judgment, run REVIEWER.md through Claude Code.")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump([asdict(f) for f in findings], fh, indent=2)
        print(f"\nWritten to {args.json}")

    if args.fail_on:
        floor = SEV_ORDER[args.fail_on]
        if any(SEV_ORDER[f.severity] >= floor for f in findings):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
