"""
Tests for topic selection — the highest-risk logic in the repo.

WHY THIS FILE EXISTS
--------------------
pick_next_topic() has already caused one production incident. The original
implementation used a stable sort, so with empty or symmetric history it
deterministically returned the same topic ('qwerty') every time. Combined with
a manual trigger landing near a scheduled one, that produced two near-identical
real posts. Fixed in 96eeefc by breaking ties with random.choice.

The function has since grown an emotion filter on top of that tie-break. It is
subtle, history-dependent, and entirely untested. That combination is how
regressions ship.

DESIGN
------
Stdlib unittest only — no pytest, no mocking, no network, no credentials.
This project stays lean deliberately; a test suite that adds a dependency is a
test suite people skip installing.

    python3 -m unittest test_topics -v      # no dependencies
    python3 -m pytest test_topics.py -v     # also works if you have pytest

Statistical tests are seeded so a failure is reproducible rather than a
"sometimes red" annoyance.
"""
from __future__ import annotations

import random
import unittest
from collections import Counter

import topics


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def history(*topic_ids: str, status: str = "posted") -> list[dict]:
    """
    Build a most-recent-first history list the way state.get_recent_history()
    returns it. Order matters: index 0 is the newest post.
    """
    out = []
    for tid in topic_ids:
        t = topics.get_topic(tid)
        assert t is not None, f"test refers to unknown topic {tid!r}"
        out.append({"topic_id": tid, "category": t["category"], "status": status})
    return out


def simulate(n: int, seed: int | None = None, window: int = 108) -> list[dict]:
    """
    Run n selections, feeding each pick back into history the way app.py does.
    `window` mirrors config.RECENT_HISTORY_WINDOW — the cap on how far back
    selection can see.
    """
    if seed is not None:
        random.seed(seed)
    hist: list[dict] = []
    picked = []
    for _ in range(n):
        t = topics.pick_next_topic(hist[:window])
        picked.append(t)
        hist.insert(0, {"topic_id": t["id"], "category": t["category"], "status": "posted"})
    return picked


# --------------------------------------------------------------------------

class TestBankIntegrity(unittest.TestCase):
    """The bank is data, and data rots quietly."""

    def test_bank_self_check_passes(self):
        self.assertEqual(topics.validate_bank(), [])

    def test_ids_unique(self):
        ids = [t["id"] for t in topics.TOPICS]
        dupes = [i for i, c in Counter(ids).items() if c > 1]
        self.assertEqual(dupes, [], f"duplicate topic ids: {dupes}")

    def test_every_category_has_multiple_topics(self):
        """
        Selection excludes the previous post's category, then picks a topic
        within the chosen one. A single-topic category repeats that topic every
        time its turn comes round.
        """
        counts = Counter(t["category"] for t in topics.TOPICS)
        thin = [c for c, n in counts.items() if n < 2]
        self.assertEqual(thin, [], f"categories with fewer than 2 topics: {thin}")

    def test_get_topic_roundtrip(self):
        for t in topics.TOPICS:
            self.assertIs(topics.get_topic(t["id"]), t)
        self.assertIsNone(topics.get_topic("no_such_topic"))


class TestCategoryRotation(unittest.TestCase):

    def test_never_repeats_previous_category(self):
        """The one hard invariant: no two consecutive posts share a category."""
        picks = simulate(200, seed=1)
        for a, b in zip(picks, picks[1:]):
            self.assertNotEqual(
                a["category"], b["category"],
                f"back-to-back category {a['category']} ({a['id']} -> {b['id']})",
            )

    def test_respects_explicit_recent_category(self):
        recent = history("doorway_effect")  # category: body
        for _ in range(40):
            self.assertNotEqual(topics.pick_next_topic(recent)["category"], "body")

    def test_all_categories_get_used(self):
        """No category should be starved by the rotation."""
        picks = simulate(300, seed=2)
        used = {t["category"] for t in picks}
        self.assertEqual(used, set(topics.CATEGORIES), f"never selected: {set(topics.CATEGORIES) - used}")


class TestTopicCycling(unittest.TestCase):

    def test_no_repeat_within_a_full_cycle(self):
        """
        With a window large enough to see a whole pass, every topic should be
        used once before any repeats.

        This is the test that fails if RECENT_HISTORY_WINDOW is set too small —
        which is exactly the live finding from review.py. Run with window=7 and
        it fails; with window >= len(TOPICS) it passes.
        """
        n = len(topics.TOPICS)
        picks = simulate(n, seed=3, window=len(topics.TOPICS) * 2)
        ids = [t["id"] for t in picks]
        repeats = [i for i, c in Counter(ids).items() if c > 1]
        self.assertEqual(repeats, [], f"repeated inside one cycle: {repeats}")

    def test_short_window_causes_early_repeats(self):
        """
        Documents the failure mode rather than asserting it's fine. If this
        ever stops finding repeats, the window/bank coupling changed and the
        production config should be re-examined.
        """
        picks = simulate(len(topics.TOPICS), seed=4, window=7)
        ids = [t["id"] for t in picks]
        self.assertLess(
            len(set(ids)), len(topics.TOPICS),
            "a 7-post window unexpectedly achieved full coverage — "
            "if selection changed, revisit config.RECENT_HISTORY_WINDOW",
        )

    def test_cycle_resets_cleanly(self):
        """After a full pass, selection keeps working instead of starving."""
        picks = simulate(len(topics.TOPICS) * 2 + 10, seed=5, window=len(topics.TOPICS) * 3)
        self.assertEqual(len(picks), len(topics.TOPICS) * 2 + 10)


class TestExcludeIds(unittest.TestCase):
    """exclude_ids is how app.py rejects a topic whose image sourcing failed."""

    def test_excluded_topic_not_returned(self):
        banned = {"doorway_effect", "earworms", "own_voice"}
        for _ in range(200):
            self.assertNotIn(topics.pick_next_topic([], exclude_ids=banned)["id"], banned)

    def test_excluding_an_entire_category_still_returns(self):
        body_ids = {t["id"] for t in topics.TOPICS if t["category"] == "body"}
        t = topics.pick_next_topic([], exclude_ids=body_ids)
        self.assertNotEqual(t["category"], "body")

    def test_excluding_everything_degrades_gracefully(self):
        """
        Rather than raising, selection abandons exclusion and returns something.
        A skipped slot is fine; a 500 from an unhandled IndexError is not.
        """
        all_ids = {t["id"] for t in topics.TOPICS}
        t = topics.pick_next_topic([], exclude_ids=all_ids)
        self.assertIn(t["id"], all_ids)

    def test_repeated_exclusion_converges(self):
        """
        Mirrors app.py's real loop: reject, re-pick, reject again. Each call
        must return something new, or the loop spins.
        """
        tried: set[str] = set()
        for _ in range(12):
            t = topics.pick_next_topic([], exclude_ids=tried)
            self.assertNotIn(t["id"], tried)
            tried.add(t["id"])


class TestEmotionRotation(unittest.TestCase):
    """Variable reward: same quality, rotating emotional flavour."""

    def test_avoids_repeating_last_emotion(self):
        picks = simulate(200, seed=6)
        repeats = sum(1 for a, b in zip(picks, picks[1:]) if a["emotion"] == b["emotion"])
        # Soft filter — it yields when filtering would empty the set — so this
        # asserts a strong reduction, not zero.
        self.assertLess(
            repeats, len(picks) * 0.10,
            f"{repeats} back-to-back emotion repeats in {len(picks)} picks — filter may be inert",
        )

    def test_filter_never_empties_candidates(self):
        """
        The defensive half of the filter. Every emotion in turn as 'last',
        against a variety of histories — selection must always return a topic.
        """
        for emotion in topics.EMOTIONS:
            sample = next((t for t in topics.TOPICS if t["emotion"] == emotion), None)
            if sample is None:
                continue
            for extra in ([], ["doorway_effect"], ["qwerty" if topics.get_topic("qwerty") else sample["id"]]):
                hist = history(sample["id"], *[e for e in extra if topics.get_topic(e)])
                self.assertIsNotNone(topics.pick_next_topic(hist))

    def test_last_emotion_ignores_skipped_entries(self):
        """
        Skipped slots aren't posts. A skipped entry must not drive the rotation,
        or one failed slot silently steers the next several picks.
        """
        sample = topics.TOPICS[0]
        skipped = [{"topic_id": sample["id"], "category": sample["category"], "status": "skipped"}]
        self.assertIsNone(topics.last_emotion(skipped))

    def test_last_emotion_reads_most_recent_post(self):
        hist = history("doorway_effect")
        self.assertEqual(topics.last_emotion(hist), topics.get_topic("doorway_effect")["emotion"])

    def test_last_emotion_survives_unknown_topic_id(self):
        """A topic removed from the bank must not crash selection on old history."""
        stale = [{"topic_id": "topic_that_was_deleted", "category": "tech", "status": "posted"}]
        self.assertIsNone(topics.last_emotion(stale))
        self.assertIsNotNone(topics.pick_next_topic(stale))


class TestFreshStartSpread(unittest.TestCase):
    """
    The regression guard for the actual production incident.

    Before 96eeefc, 30 fresh-start trials returned the same topic 30 times.
    A stable sort over an empty history is fully deterministic, so every fresh
    deploy — and every instance that started before Firestore had been written
    — picked identically.
    """

    def test_empty_history_spreads_across_topics(self):
        random.seed(7)
        picks = [topics.pick_next_topic([])["id"] for _ in range(60)]
        distinct = len(set(picks))
        self.assertGreater(
            distinct, 10,
            f"only {distinct} distinct topics from 60 fresh starts — "
            "the tie-break may have regressed to deterministic (see incident 96eeefc)",
        )

    def test_empty_history_spreads_across_categories(self):
        random.seed(8)
        cats = {topics.pick_next_topic([])["category"] for _ in range(60)}
        self.assertGreater(len(cats), len(topics.CATEGORIES) // 2, f"fresh starts clustered into {cats}")

    def test_no_single_topic_dominates(self):
        """Even distribution matters more than mere variety."""
        random.seed(9)
        picks = Counter(topics.pick_next_topic([])["id"] for _ in range(200))
        top_id, top_n = picks.most_common(1)[0]
        self.assertLess(top_n / 200, 0.25, f"{top_id} took {top_n/200:.0%} of fresh starts")


class TestHistoryShapeTolerance(unittest.TestCase):
    """
    History comes from Firestore and from local JSON, written across multiple
    code versions. Selection must not crash on an entry it doesn't recognise.
    """

    def test_empty_history(self):
        self.assertIsNotNone(topics.pick_next_topic([]))

    def test_history_missing_status_field(self):
        """Entries written before record_post included status."""
        t = topics.TOPICS[0]
        hist = [{"topic_id": t["id"], "category": t["category"]}]
        self.assertIsNotNone(topics.pick_next_topic(hist))

    def test_history_with_unknown_category(self):
        """A category retired from the bank must not poison selection."""
        hist = [{"topic_id": "gone", "category": "trivia", "status": "posted"}]
        self.assertIsNotNone(topics.pick_next_topic(hist))

    def test_history_longer_than_bank(self):
        picks = simulate(len(topics.TOPICS) * 3, seed=10, window=len(topics.TOPICS) * 4)
        self.assertEqual(len(picks), len(topics.TOPICS) * 3)


class TestPhotoTopicIntegrity(unittest.TestCase):
    """images.py indexes photo_subject directly — a missing key is a 500."""

    def test_photo_topics_have_required_fields(self):
        for t in topics.TOPICS:
            if t["image_type"] == "photo":
                self.assertTrue(t.get("photo_keywords"), f"{t['id']} missing photo_keywords")
                self.assertTrue(t.get("photo_subject"), f"{t['id']} missing photo_subject")

    def test_photo_subject_is_a_single_word(self):
        """
        _matches_subject() does substring matching with naive plural handling.
        A multi-word subject rarely appears verbatim in a stock-photo caption,
        so it silently fails every candidate and the slot dies on image sourcing.
        """
        for t in topics.TOPICS:
            if t["image_type"] == "photo":
                self.assertEqual(
                    len(t["photo_subject"].split()), 1,
                    f"{t['id']}: photo_subject {t['photo_subject']!r} is multi-word; "
                    "_matches_subject will almost never match it",
                )

    def test_diagram_topics_dont_carry_photo_fields(self):
        for t in topics.TOPICS:
            if t["image_type"] == "diagram":
                self.assertNotIn("photo_keywords", t, f"{t['id']} is a diagram but has photo_keywords")


class TestContentInvariants(unittest.TestCase):
    """
    The prompts index these fields directly. A missing one is an unhandled
    KeyError inside a scheduled run at 9am.
    """

    def test_all_prompt_fields_present_and_nonempty(self):
        required = ("prompt", "universal_door", "hook_seed", "dinner_table_line", "emotion")
        for t in topics.TOPICS:
            for field in required:
                self.assertTrue(str(t.get(field, "")).strip(), f"{t['id']} has empty {field}")

    def test_hook_seed_respects_effort_budget(self):
        """The hook is the product. Over-long seeds push the generator over budget."""
        for t in topics.TOPICS:
            words = len(t["hook_seed"].split())
            self.assertLessEqual(words, 14, f"{t['id']}: hook_seed is {words} words")

    def test_dinner_table_line_is_retellable_length(self):
        """
        Calibration showed the critic accepting 40-word passages as 'the
        retellable sentence'. The bank's own reference lines must not model
        that failure — the generator is shown them as the target.
        """
        for t in topics.TOPICS:
            words = len(t["dinner_table_line"].split())
            self.assertLessEqual(
                words, 30,
                f"{t['id']}: dinner_table_line is {words} words — too long to model a gift",
            )

    def test_emotions_are_known(self):
        for t in topics.TOPICS:
            self.assertIn(t["emotion"], topics.EMOTIONS, f"{t['id']} has unknown emotion")


if __name__ == "__main__":
    unittest.main(verbosity=2)
