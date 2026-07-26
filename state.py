"""Post-history state: which topics/categories have run recently, plus a full
audit log of what was posted (or skipped). Backed by Firestore in production;
falls back to a local JSON file when FIRESTORE_PROJECT_ID isn't set, so the
pipeline is runnable before any GCP resources exist.
"""
import json
import os
from datetime import datetime, timezone

import config

_LOCAL_STATE_FILE = "local_state.json"
_COLLECTION = "post_history"


def _use_firestore() -> bool:
    return bool(config.FIRESTORE_PROJECT_ID)


def _load_local() -> list[dict]:
    if not os.path.exists(_LOCAL_STATE_FILE):
        return []
    with open(_LOCAL_STATE_FILE, "r") as f:
        return json.load(f)


def _save_local(entries: list[dict]) -> None:
    with open(_LOCAL_STATE_FILE, "w") as f:
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

    entries = _load_local()
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

    entries = _load_local()
    entries.append(entry)
    _save_local(entries)
