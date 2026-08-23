"""One-shot local dry-run of the idiom pipeline for every idiom in the bank:
generate -> critic (with retry hints, same loop shape as run_idiom_pipeline)
-> image. Prints drafts, critic scores, and image paths. Posts nothing,
records nothing.

Usage: python3 dry_run_idioms.py [--skip-images]
"""
from __future__ import annotations

import sys

import config
import idiom_generate
import idiom_prompt
from idiom_images import IdiomImageError
from idiom_topics import IDIOM_TOPICS

skip_images = "--skip-images" in sys.argv or not config.GEMINI_API_KEY

# With a 30-idiom bank, a full run costs real money -- pass ids to test a
# subset (python3 dry_run_idioms.py let_cat_out_bag paint_town_red).
_ids = [a for a in sys.argv[1:] if not a.startswith("-")]
_to_run = [t for t in IDIOM_TOPICS if not _ids or t["id"] in _ids]

for topic in _to_run:
    print("=" * 72)
    print(f"IDIOM: {topic['idiom']}  ({topic['id']}, confidence={topic['confidence']})")
    print("=" * 72)

    retry_hint = ""
    draft, scores, passed, reasons = "", None, False, []
    for attempt in range(1, config.MAX_GENERATION_ATTEMPTS + 1):
        draft = idiom_generate.generate_idiom_draft(topic, retry_hint)
        passed, reasons, scores = idiom_generate.validate_idiom_draft(draft, topic)
        print(f"\n--- attempt {attempt}: {'PASS' if passed else 'FAIL'}")
        if passed:
            break
        print("    reasons:", reasons)
        retry_hint = idiom_prompt.build_retry_hint(scores) if scores else ""

    print(f"\nDRAFT ({len(draft.split())} words):\n{draft}\n")
    if scores:
        print("CRITIC:")
        print(f"  accuracy_ok:      {scores.get('historical_accuracy_ok')}")
        print(f"  condescension_ok: {scores.get('no_condescension_ok')}")
        print(f"  retellability:    {scores.get('retellability')}")
        print(f"  fluency:          {scores.get('fluency')}")
        print(f"  gift:             {scores.get('dinner_table_sentence')!r}")
        if not passed:
            print(f"  FINAL VERDICT: FAILED after {config.MAX_GENERATION_ATTEMPTS} attempts: {reasons}")

    if skip_images:
        print("IMAGE: skipped (GEMINI_API_KEY not set)" if not config.GEMINI_API_KEY
              else "IMAGE: skipped (--skip-images)")
    else:
        try:
            path = idiom_generate.source_idiom_image(topic)
            print(f"IMAGE: {path}")
        except IdiomImageError as e:
            print(f"IMAGE FAILED (would ship text-only): {e}")
    print()
