"""Post-history state: which topics/categories have run recently, plus a full
audit log of what was posted (or skipped). Backed by Firestore in production;
falls back to a local JSON file when FIRESTORE_PROJECT_ID isn't set, so the
pipeline is runnable before any GCP resources exist.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import config
from validate_prompt import log_fields

_LOCAL_STATE_FILE = "local_state.json"
_LOCAL_DRAFTS_FILE = "local_drafts.json"
_COLLECTION = "post_history"
_DRAFTS_COLLECTION = "draft_log"


def _use_firestore() -> bool:
    return bool(config.FIRESTORE_PROJECT_ID)


def _load_local(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)


def _save_local(path: str, entries: list[dict]) -> None:
    with open(path, "w") as f:
        json.dump(entries, f, indent=2)


def get_recent_history(limit: int = config.RECENT_HISTORY_WINDOW) -> list[dict]:
    """Returns most-recent-first list of {"topic_id", "category", "date"}."""
    if _use_firestore():
        from google.cloud import firestore

        db = firestore.Client(project=config.FIRESTORE_PROJECT_ID)
        docs = (
            db.collection(_COLLECTION)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [d.to_dict() for d in docs]

    entries = _load_local(_LOCAL_STATE_FILE)
    entries.sort(key=lambda e: e.get("date", ""), reverse=True)
    return entries[:limit]


def record_post(entry: dict) -> None:
    """entry: {"topic_id", "category", "status" ("posted"/"skipped"),
    "tweet_id", "image_source", "opening_line", ...}"""
    entry = {**entry, "date": datetime.now(timezone.utc).isoformat()}

    if _use_firestore():
        from google.cloud import firestore

        db = firestore.Client(project=config.FIRESTORE_PROJECT_ID)
        entry["created_at"] = firestore.SERVER_TIMESTAMP
        db.collection(_COLLECTION).add(entry)
        return

    entries = _load_local(_LOCAL_STATE_FILE)
    entries.append(entry)
    _save_local(_LOCAL_STATE_FILE, entries)


def record_draft(
    topic_id: str,
    category: str,
    passed: bool,
    reasons: list[str],
    scores: dict | None,
    fmt: str = "everyday",
    score_fields: dict | None = None,
) -> None:
    """Persist every generation attempt, including rejected drafts, which
    previously weren't recorded at all. This is the dataset that makes it
    possible to check whether critic scores predict real engagement, and
    retune thresholds (validate_prompt.THRESHOLDS) from data instead of
    intuition.

    `scores` is None when the draft was rejected by the rule-based layer
    before any critic call was made.

    `fmt` tags the content format ("everyday" | "idiom") so the two formats'
    performance can be separated in analysis. `score_fields` lets a format
    with different critic axes (idiom_prompt.log_fields) pass its own
    pre-flattened fields; when omitted, the five-beat log_fields applies.
    """
    entry = {
        "topic_id": topic_id,
        "category": category,
        "format": fmt,
        "passed": passed,
        "reasons": reasons,
        "date": datetime.now(timezone.utc).isoformat(),
    }
    if score_fields is not None:
        entry.update(score_fields)
    elif scores is not None:
        entry.update(log_fields(scores, passed, reasons))

    if _use_firestore():
        from google.cloud import firestore

        db = firestore.Client(project=config.FIRESTORE_PROJECT_ID)
        entry["created_at"] = firestore.SERVER_TIMESTAMP
        db.collection(_DRAFTS_COLLECTION).add(entry)
        return

    entries = _load_local(_LOCAL_DRAFTS_FILE)
    entries.append(entry)
    _save_local(_LOCAL_DRAFTS_FILE, entries)


# --------------------------------------------------------------------------
# Idiom support: full idiom history + a queue of researched idioms
# --------------------------------------------------------------------------
# get_recent_history() is a fixed-size window over ALL formats; idiom
# selection needs the complete idiom record (a finite window quietly forgets
# old idioms, which is how repeats creep in), so it reads idiom records
# directly.

_LOCAL_QUEUE_FILE = "local_idiom_queue.json"
_QUEUE_COLLECTION = "idiom_queue"


def get_idiom_history() -> list[dict]:
    """Every idiom-format post_history record (posted and skipped), most
    recent first. No size cap -- the idiom record is small and selection
    correctness depends on seeing all of it."""
    if _use_firestore():
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        db = firestore.Client(project=config.FIRESTORE_PROJECT_ID)
        docs = db.collection(_COLLECTION).where(filter=FieldFilter("format", "==", "idiom")).stream()
        entries = [d.to_dict() for d in docs]
    else:
        entries = [e for e in _load_local(_LOCAL_STATE_FILE) if e.get("format") == "idiom"]
    entries.sort(key=lambda e: e.get("date", ""), reverse=True)
    return entries


def queue_all() -> list[dict]:
    """Every researched-idiom queue entry (any status), oldest first. Each
    dict carries its own `id`."""
    if _use_firestore():
        from google.cloud import firestore

        db = firestore.Client(project=config.FIRESTORE_PROJECT_ID)
        entries = []
        for d in db.collection(_QUEUE_COLLECTION).stream():
            entry = d.to_dict()
            entry["id"] = d.id
            entries.append(entry)
    else:
        entries = _load_local(_LOCAL_QUEUE_FILE)
    entries.sort(key=lambda e: e.get("researched_at", ""))
    return entries


def queue_put(entry: dict) -> None:
    """Insert or overwrite one queue entry, keyed by entry["id"]."""
    entry = {**entry, "researched_at": entry.get("researched_at") or datetime.now(timezone.utc).isoformat()}
    if _use_firestore():
        from google.cloud import firestore

        db = firestore.Client(project=config.FIRESTORE_PROJECT_ID)
        db.collection(_QUEUE_COLLECTION).document(entry["id"]).set(entry)
        return

    entries = [e for e in _load_local(_LOCAL_QUEUE_FILE) if e.get("id") != entry["id"]]
    entries.append(entry)
    _save_local(_LOCAL_QUEUE_FILE, entries)
