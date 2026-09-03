"""
Critic calibration harness.

THE PROBLEM THIS EXISTS TO CATCH
--------------------------------
A critic that passes everything is not a gate. The first three live drafts all
scored 9s and 10s with comments like "none — this is exceptional", which is
either (a) a genuinely excellent generator or (b) an agreeable critic. Those
two look identical from a sample of passes only.

The only way to tell them apart is to show the critic drafts that are
*definitely bad* and see whether it notices. This script does that.

WHAT IT RUNS
------------
1. CONTROLS — hand-written drafts with known defects, each targeting one
   specific gate. If the critic passes any of these, the gate is broken and
   nothing should ship until it is fixed.
2. REAL DRAFTS — n live generations across the bank, using the real
   pipeline (generate -> validate), so the score distribution can be read.

It never posts, never touches Firestore, and never writes to local_state.json.

USAGE
-----
    cd ~/Development/lyfzaxi10tal
    python calibrate.py                 # 5 controls + 20 real drafts
    python calibrate.py --drafts 10     # fewer real drafts (cheaper)
    python calibrate.py --controls-only # just the controls, ~10 API calls
    python calibrate.py --json out.json # also dump raw results

COST
----
Each real draft is one Sonnet call plus one Haiku call. 20 drafts is a few
cents. Controls are Haiku only.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter

import config
import generate
import topic_generate
import validate
from validate_prompt import THRESHOLDS

# Real topic dicts, preserved from the retired topics.py bank so the
# CONTROLS below (each targeting a specific gate against a specific real
# topic) keep working without depending on that file. Extracted once when
# the bank was removed in favor of topic_generate.py's dynamic generation --
# not maintained as a living bank, just fixed fixtures for these six checks.
_CONTROL_TOPICS = {
    "sharding": {
        "id": "sharding", "category": "tech",
        "prompt": "Sharding and horizontal scale: no single machine could serve everyone, so data is split across many. Explain via one librarian versus a library split into rooms by surname.",
        "universal_door": "Two billion people open the same app at breakfast.",
        "hook_seed": "Two billion people open Instagram at breakfast. It doesn't collapse.",
        "dinner_table_line": "There is no 'the server' — you and your neighbour are being served by completely different machines.",
        "emotion": "awe", "image_type": "diagram",
    },
    "cloudy_ice": {
        "id": "cloudy_ice", "category": "science",
        "prompt": "Ice freezes from the outside in, pushing dissolved air and impurities to the last-frozen centre — the cloud is trapped gas.",
        "universal_door": "Home ice cubes are cloudy; bar ice is clear.",
        "hook_seed": "Your ice cubes are cloudy in the middle. Bar ice isn't.",
        "dinner_table_line": "That cloud is trapped air — clear ice is just ice that was frozen slowly enough for the air to escape.",
        "emotion": "surprise", "image_type": "photo",
        "photo_keywords": "ice cubes glass close up", "photo_subject": "ice",
    },
    "bread_stales_fridge": {
        "id": "bread_stales_fridge", "category": "science",
        "prompt": "Staling is starch retrogradation, not drying — and it runs fastest just above freezing, so the fridge is the worst place for bread.",
        "universal_door": "Putting bread in the fridge to keep it fresh.",
        "hook_seed": "The fridge is the worst possible place for bread.",
        "dinner_table_line": "Bread goes stale fastest at fridge temperature — the freezer is fine, the counter is fine, the fridge is the one bad option.",
        "emotion": "wrong", "image_type": "photo",
        "photo_keywords": "sliced bread loaf", "photo_subject": "bread",
    },
    "doorway_effect": {
        "id": "doorway_effect", "category": "body",
        "prompt": "The doorway effect: memory is chunked by context, and physically crossing a boundary flushes the working-memory buffer tied to the previous room.",
        "universal_door": "Walking into a room and instantly forgetting why.",
        "hook_seed": "You walk into the kitchen and forget why. Every time.",
        "dinner_table_line": "It isn't your memory failing — the doorway itself wipes it, and walking back actually helps.",
        "emotion": "surprise", "image_type": "diagram",
    },
    "weep_holes": {
        "id": "weep_holes", "category": "everyday",
        "prompt": "Weep holes: small gaps left in brickwork let trapped moisture drain and ventilate the cavity behind the wall.",
        "universal_door": "Small holes in the brick wall of almost every building.",
        "hook_seed": "Those little holes in brick walls aren't mistakes.",
        "dinner_table_line": "Every brick wall needs to breathe — seal those holes and the wall rots from inside.",
        "emotion": "surprise", "image_type": "photo",
        "photo_keywords": "brick wall weep holes mortar", "photo_subject": "brick",
    },
    "onion_tears": {
        "id": "onion_tears", "category": "science",
        "prompt": "Cutting ruptures cells, releasing enzymes that form a volatile sulfur compound; it reacts with eye moisture to form a mild acid, and tears are the flush response.",
        "universal_door": "Crying over a chopping board.",
        "hook_seed": "Onions don't make you cry. They make acid in your eyes.",
        "dinner_table_line": "The onion is releasing a gas that turns into acid the moment it touches your eye — the tears are your body rinsing it out.",
        "emotion": "alarm", "image_type": "photo",
        "photo_keywords": "chopped onion cutting board", "photo_subject": "onion",
    },
}


# ==========================================================================
# CONTROLS
# ==========================================================================
# Each control is deliberately broken in ONE specific way, so a failure is
# diagnostic rather than vague. `expect_fail_on` names the gate that should
# catch it — if the critic fails the draft for a *different* reason, that's
# still a pass for our purposes, but it's worth eyeballing.
#
# These are written to be otherwise competent: fluent prose, correct facts,
# reasonable length. A critic that only catches sloppy writing will pass them,
# which is exactly the failure mode we're hunting.

CONTROLS = [
    {
        "name": "jargon-door (the v1 failure mode)",
        "expect_fail_on": "universality",
        "topic_id": "sharding",
        "draft": (
            "Database sharding is how large systems split their data across many machines.\n\n"
            "The idea is straightforward once you see it. A single database server has a hard "
            "ceiling — there is only so much disk, so much memory, so many connections it can "
            "hold open at once. Past that point you cannot buy your way out with a bigger box.\n\n"
            "So instead of one machine holding everything, the data is partitioned horizontally. "
            "Each shard holds a slice of the rows, and a routing layer decides which shard a given "
            "query should go to. Add more traffic, add more shards.\n\n"
            "It's why services with enormous user counts stay responsive. There is no single "
            "server under all that load, because there is no single server at all.\n\n"
            "Sharding is one of those ideas that sounds complicated and turns out to be mostly "
            "common sense applied at scale."
        ),
    },
    {
        "name": "no-gift (nothing retellable)",
        "expect_fail_on": "retellability",
        "topic_id": "cloudy_ice",
        "draft": (
            "Your ice cubes are cloudy in the middle. Bar ice isn't.\n\n"
            "There are a few things going on here, and they interact in ways that make it hard to "
            "point at one single cause. Water contains dissolved gases. It also contains minerals, "
            "depending on where you live and how your supply is treated. When water freezes, the "
            "process doesn't happen everywhere at once.\n\n"
            "The outer layers solidify first. As they do, the things that aren't water get pushed "
            "inward, because they don't fit into the crystal structure that's forming. Over time "
            "this concentrates them toward the centre. Rate matters too, since faster freezing "
            "traps more of what would otherwise escape.\n\n"
            "Commercial ice makers work differently. They use directional freezing and moving water, "
            "which changes where things end up. The result looks different for reasons that follow "
            "from all of the above.\n\n"
            "It's a small thing, but it's the kind of small thing that has more going on inside it "
            "than you'd expect."
        ),
    },
    {
        # v1 of this control used the sixty_seconds topic and claimed nothing
        # was overturned — but "your clock runs on 4,000-year-old Babylonian
        # math" IS a prediction violation for most readers, so the control was
        # testing a true positive rather than a planted defect. Scores across
        # seven calibration runs sat right on the threshold (6,6,8,8,8,7,8)
        # because the draft genuinely belonged there. Replaced with content
        # that states only what a reader would already confidently predict.
        "name": "no-violation (informative, overturns nothing)",
        "expect_fail_on": "prediction_violation",
        "topic_id": "bread_stales_fridge",
        "draft": (
            "A refrigerator keeps food fresh by slowing down bacteria.\n\n"
            "Bacteria are living things, and like most living things, they multiply fastest when "
            "it's warm. A refrigerator works by lowering the temperature, and the cold simply slows "
            "that process down. Mold and the enzymes that break food down work the same way — cold "
            "makes them sluggish, it doesn't stop them, which is why food in the fridge still "
            "eventually spoils.\n\n"
            "This is also why food left out on a hot day goes off faster than food left out on a "
            "cool day. More heat means faster microbial activity. Less heat means slower activity. "
            "The relationship runs exactly the way you'd expect.\n\n"
            "Freezers take the same idea further. At freezing temperatures, bacterial growth nearly "
            "stops altogether, which is why frozen food lasts so much longer than refrigerated food. "
            "It's the same principle, just colder.\n\n"
            "So a fridge isn't doing anything mysterious. It's cold enough to make bacteria "
            "sluggish, and that sluggishness is what keeps your food edible for longer."
        ),
    },
    {
        "name": "long-hook (fluency: 30-word opening line)",
        "expect_fail_on": "fluency",
        "topic_id": "doorway_effect",
        "draft": (
            "There is a very common experience, one that almost everybody has had at some point in "
            "their lives, where you walk from one room into another room and immediately forget the "
            "reason you went there.\n\n"
            "Most people quietly decide this is a sign of getting older. It isn't.\n\n"
            "Your memory doesn't store things in one long strip. It stores them in chunks, and the "
            "chunks are tied to where you were when you made them. The room is part of the file. So "
            "when you cross a doorway, your brain decides the previous context is finished and clears "
            "the desk for the new one.\n\n"
            "Which is why walking back sometimes works. You're reopening the file.\n\n"
            "It isn't your memory failing. It's a doorway doing exactly what it's supposed to."
        ),
    },
    {
        "name": "flat-affect (correct, fluent, zero arousal)",
        "expect_fail_on": "arousal",
        "topic_id": "weep_holes",
        "draft": (
            "Those small holes in brick walls aren't mistakes.\n\n"
            "They're called weep holes, and they're a standard part of how a cavity wall is built. "
            "The gaps are left deliberately in the mortar, usually near the base of the wall and "
            "above openings like windows and doors.\n\n"
            "Their function is drainage and ventilation. Moisture gets into the cavity behind the "
            "outer layer of brick, whether from driving rain or from condensation, and it needs a "
            "route back out. The holes provide that route. They also allow a small amount of air "
            "movement, which helps the cavity dry.\n\n"
            "Building codes in most places specify their spacing and placement. Filling them in is "
            "generally discouraged, since trapped moisture can lead to damage over time.\n\n"
            "So the holes are doing a job, and it's a fairly important one."
        ),
    },
    {
        "name": "structure-violation (hard fail: visible labels)",
        "expect_fail_on": "hard_failures",
        "topic_id": "onion_tears",
        "draft": (
            "What it is: Onions release a gas when you cut them.\n\n"
            "How it works: Cutting ruptures cells and mixes two chemicals that were kept apart. The "
            "reaction produces a volatile sulfur compound that drifts upward.\n\n"
            "Why it matters: When that gas reaches your eye, it meets moisture and forms a mild acid. "
            "Your eyes flood in response, washing it away.\n\n"
            "The gotcha: Chilling the onion helps because cold gas drifts less. A sharper knife helps "
            "more, because it slices cells rather than crushing them.\n\n"
            "So the onion isn't upsetting you. It's defending itself."
        ),
    },
]


# ==========================================================================
# Runners
# ==========================================================================

def _fmt_scores(scores: dict | None) -> str:
    if not scores:
        return "  (rule-based rejection — no critic call)"
    return "  U:{universality:<2} PV:{prediction_violation:<2} F:{fluency:<2} A:{arousal:<2} R:{retellability:<2}".format(
        universality=scores.get("universality", "?"),
        prediction_violation=scores.get("prediction_violation", "?"),
        fluency=scores.get("fluency", "?"),
        arousal=scores.get("arousal", "?"),
        retellability=scores.get("retellability", "?"),
    )


def run_controls() -> list[dict]:
    print("=" * 78)
    print("CONTROLS — these SHOULD ALL FAIL. Any pass means the gate is broken.")
    print("=" * 78)

    results = []
    for ctrl in CONTROLS:
        topic = _CONTROL_TOPICS.get(ctrl["topic_id"])
        if topic is None:
            print(f"\n!! skipping {ctrl['name']}: no fixture topic '{ctrl['topic_id']}'")
            continue

        try:
            passed, reasons, scores = validate.validate_draft(ctrl["draft"], topic, [])
        except Exception as e:  # noqa: BLE001 — one flaky critic call shouldn't abort the whole suite
            print(f"\n[{ctrl['name']}]")
            print(f"  target gate: {ctrl['expect_fail_on']}")
            print(f"  ERROR: {e}")
            results.append({
                "kind": "control",
                "name": ctrl["name"],
                "expect_fail_on": ctrl["expect_fail_on"],
                "passed": None,
                "reasons": [f"error: {e}"],
                "scores": None,
            })
            continue

        verdict = "*** PASSED (BAD) ***" if passed else "correctly rejected"

        print(f"\n[{ctrl['name']}]")
        print(f"  target gate: {ctrl['expect_fail_on']}")
        print(f"  {verdict}")
        print(_fmt_scores(scores))
        if reasons:
            for r in reasons[:4]:
                print(f"    - {r}")

        results.append({
            "kind": "control",
            "name": ctrl["name"],
            "expect_fail_on": ctrl["expect_fail_on"],
            "passed": passed,
            "reasons": reasons,
            "scores": scores,
        })
    return results


def run_real_drafts(n: int) -> list[dict]:
    print()
    print("=" * 78)
    print(f"REAL DRAFTS — {n} live generations")
    print("=" * 78)

    # No fixed bank to sample from anymore -- generate n fresh candidates via
    # topic_generate directly, rotating the "avoid this category" hint across
    # picks so the distribution isn't dominated by one category. Skips
    # topic_generate's own gate deliberately: this harness calibrates the
    # DRAFT critic, not the topic gate, so a topic doesn't need to have
    # passed that gate to be a useful draft-critic test case.
    cats = topic_generate.CATEGORIES
    picks = []
    for i in range(n):
        try:
            picks.append(topic_generate.generate_candidate(digest=[], last_category=cats[i % len(cats)]))
        except Exception as e:  # noqa: BLE001 — one flaky call shouldn't abort the whole suite
            print(f"\n!! topic generation failed for pick {i + 1}: {e}")

    results = []
    for idx, topic in enumerate(picks, 1):
        try:
            draft = generate.generate_draft(topic, [], "")
            passed, reasons, scores = validate.validate_draft(draft, topic, [])
        except Exception as e:  # noqa: BLE001 — a calibration run shouldn't die on one bad call
            print(f"\n[{idx}/{len(picks)}] {topic['id']} — ERROR: {e}")
            continue

        status = "PASS" if passed else "fail"
        print(f"\n[{idx}/{len(picks)}] {topic['id']} ({topic['category']}, {topic['emotion']}) — {status}")
        print(_fmt_scores(scores))
        if scores and scores.get("dinner_table_sentence"):
            print(f'    gift: "{scores["dinner_table_sentence"]}"')
        if reasons:
            for r in reasons[:3]:
                print(f"    - {r}")

        results.append({
            "kind": "real",
            "topic_id": topic["id"],
            "category": topic["category"],
            "emotion": topic["emotion"],
            "passed": passed,
            "reasons": reasons,
            "scores": scores,
            "draft": draft,
        })
    return results


# ==========================================================================
# Report
# ==========================================================================

def report(controls: list[dict], reals: list[dict]) -> int:
    """Prints the verdict. Returns a shell exit code."""
    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)

    exit_code = 0

    # --- controls ---
    leaked = [c for c in controls if c["passed"] is True]
    errored = [c for c in controls if c["passed"] is None]
    rejected = [c for c in controls if c["passed"] is False]
    if controls:
        print(f"\nControls: {len(rejected)}/{len(controls)} correctly rejected")
        if errored:
            print(f"  ({len(errored)} errored and were not scored — not counted as pass or fail):")
            for c in errored:
                print(f"    - {c['name']}: {c['reasons'][0] if c['reasons'] else 'unknown error'}")
        if leaked:
            exit_code = 1
            print("\n  *** THE GATE IS NOT WORKING. These bad drafts passed: ***")
            for c in leaked:
                print(f"    - {c['name']}  (should have failed on {c['expect_fail_on']})")
            print("\n  Do not ship. The critic is agreeing rather than evaluating.")
            print("  Fix: raise the relevant THRESHOLDS, or sharpen that gate's wording")
            print("  in CRITIC_SYSTEM_PROMPT so the failure mode is described explicitly.")
        elif not errored:
            print("  Every planted defect was caught. The gate discriminates.")

    if not reals:
        return exit_code

    # --- pass rate ---
    passes = [r for r in reals if r["passed"]]
    rate = len(passes) / len(reals) * 100
    print(f"\nReal drafts: {len(passes)}/{len(reals)} passed ({rate:.0f}%)")

    if rate == 100:
        print("  ! 100% pass rate. Either the generator is excellent or the gate is loose.")
        print("    The controls above are what tell you which. If controls all failed")
        print("    correctly, this is real — but watch it over the next 20.")
    elif rate < 40:
        print("  ! Under 40% passing. The gate is likely too tight — you'll skip slots")
        print("    on technicalities. Consider lowering the weakest-link threshold by 1.")
    else:
        print("  Pass rate is in a healthy band (roughly 40-85% is where a real gate sits).")

    # --- score distribution ---
    print("\nScore distribution (real drafts):")
    print(f"  {'axis':<22} {'min':>4} {'med':>4} {'max':>4}   {'floor':>5}  spread")
    for axis, floor in THRESHOLDS.items():
        vals = sorted(r["scores"][axis] for r in reals if r["scores"] and r["scores"].get(axis) is not None)
        if not vals:
            continue
        med = vals[len(vals) // 2]
        spread = vals[-1] - vals[0]
        flag = "  <- no variance" if spread == 0 else ("  <- narrow" if spread == 1 else "")
        print(f"  {axis:<22} {vals[0]:>4} {med:>4} {vals[-1]:>4}   {floor:>5}{flag}")

    flat = [
        a for a in THRESHOLDS
        if len({r["scores"][a] for r in reals if r["scores"] and r["scores"].get(a) is not None}) <= 1
    ]
    if flat:
        print(f"\n  ! No variance on: {', '.join(flat)}")
        print("    An axis that returns the same number every time is not measuring anything.")
        print("    Either every draft genuinely sits there, or the critic is anchoring.")

    # --- what's actually binding ---
    print("\nWhich gate is doing the work:")
    binding = Counter()
    for r in reals:
        if r["passed"] or not r["scores"]:
            continue
        for axis, floor in THRESHOLDS.items():
            v = r["scores"].get(axis)
            if v is not None and v < floor:
                binding[axis] += 1
    if binding:
        for axis, count in binding.most_common():
            print(f"  {axis:<22} blocked {count}")
    else:
        print("  Nothing blocked anything. No gate is currently binding.")

    # --- per-category ---
    print("\nBy category:")
    cats: dict[str, list] = {}
    for r in reals:
        cats.setdefault(r["category"], []).append(r)
    for cat in sorted(cats):
        rs = cats[cat]
        p = sum(1 for r in rs if r["passed"])
        avg_u = [r["scores"]["universality"] for r in rs if r["scores"] and r["scores"].get("universality")]
        u = f"{sum(avg_u)/len(avg_u):.1f}" if avg_u else "  -"
        print(f"  {cat:<12} {p}/{len(rs)} passed   avg universality {u}")

    print("\nNext: read the gift lines above. If you can't picture yourself saying one")
    print("out loud at a table, the critic scored it too generously regardless of the")
    print("number it gave. That judgment is yours, not the model's.")

    return exit_code


def main() -> int:
    ap = argparse.ArgumentParser(description="Calibrate the concept-bot critic gate.")
    ap.add_argument("--drafts", type=int, default=20, help="how many real drafts to generate")
    ap.add_argument("--controls-only", action="store_true", help="skip real generation")
    ap.add_argument("--json", metavar="PATH", help="dump raw results here")
    ap.add_argument("--seed", type=int, help="seed the topic sampling for a repeatable run")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    if not config.ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY is not set — check your .env", file=sys.stderr)
        return 2

    controls = run_controls()
    reals = [] if args.controls_only else run_real_drafts(args.drafts)

    code = report(controls, reals)

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"controls": controls, "real": reals}, f, indent=2)
        print(f"\nRaw results written to {args.json}")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
