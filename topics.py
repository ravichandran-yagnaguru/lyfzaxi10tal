"""Topic bank + selection logic. Selection reads recent post history (passed in
from state.py) so it can avoid repeating a category back-to-back and avoid
reusing a topic until the bank cycles.
"""

TOPICS = [
    # --- tech / systems ---
    {"id": "cfs_scheduler", "category": "tech", "prompt": "the Linux CFS (Completely Fair Scheduler) and how it decides which process runs next", "image_type": "diagram"},
    {"id": "keda", "category": "tech", "prompt": "KEDA (Kubernetes Event-Driven Autoscaling) and how it scales workloads based on event/queue depth instead of just CPU", "image_type": "diagram"},
    {"id": "ocr", "category": "tech", "prompt": "OCR (optical character recognition) and how software turns a photo of text into actual editable text", "image_type": "photo", "photo_keywords": "scanning document text closeup"},
    {"id": "iac", "category": "tech", "prompt": "infrastructure as code (IaC) and why teams describe servers/cloud resources in text files instead of clicking through a console", "image_type": "diagram"},
    {"id": "backpressure", "category": "tech", "prompt": "backpressure in software systems, and what happens when a fast producer overwhelms a slow consumer", "image_type": "diagram"},
    {"id": "circuit_breaker", "category": "tech", "prompt": "the circuit breaker pattern in distributed systems and how it stops one failing service from taking down everything else", "image_type": "diagram"},
    {"id": "indexing", "category": "tech", "prompt": "database indexing and why looking something up by an indexed column is so much faster than a full table scan", "image_type": "photo", "photo_keywords": "book index pages"},
    {"id": "partitioning", "category": "tech", "prompt": "database partitioning and how splitting one huge table into smaller chunks speeds things up", "image_type": "diagram"},
    {"id": "sharding", "category": "tech", "prompt": "database sharding and how it spreads data across multiple machines instead of one", "image_type": "diagram"},
    {"id": "rag", "category": "tech", "prompt": "RAG (retrieval-augmented generation) and how it lets an AI model answer using documents it was never trained on", "image_type": "diagram"},
    {"id": "embeddings", "category": "tech", "prompt": "embeddings and how turning words into lists of numbers lets computers tell that 'dog' and 'puppy' are related", "image_type": "diagram"},
    {"id": "cdn", "category": "tech", "prompt": "CDNs (content delivery networks) and why a video loads faster when a copy is sitting physically closer to you", "image_type": "diagram"},
    {"id": "idempotency", "category": "tech", "prompt": "idempotency in APIs and why retrying a request safely shouldn't double-charge or double-create anything", "image_type": "diagram"},
    {"id": "cgroups", "category": "tech", "prompt": "Linux cgroups and how they let the OS put a hard limit on how much CPU/memory one process is allowed to hog", "image_type": "diagram"},

    # --- psychology ---
    {"id": "zeigarnik", "category": "psychology", "prompt": "the Zeigarnik effect: why unfinished tasks nag at your memory way more than finished ones", "image_type": "diagram"},
    {"id": "dunning_kruger", "category": "psychology", "prompt": "the Dunning-Kruger effect and why people with the least skill in something are often the most confident about it", "image_type": "diagram"},
    {"id": "placebo_effect", "category": "psychology", "prompt": "the placebo effect and how a fake treatment with no active ingredient can still measurably help people feel better", "image_type": "photo", "photo_keywords": "white pills bottle"},
    {"id": "bystander_effect", "category": "psychology", "prompt": "the bystander effect and why someone is less likely to help in an emergency the more other people are standing around", "image_type": "photo", "photo_keywords": "crowd of people city street"},
    {"id": "baader_meinhof", "category": "psychology", "prompt": "the Baader-Meinhof phenomenon (frequency illusion): why you suddenly start noticing something everywhere right after you first learn about it", "image_type": "photo", "photo_keywords": "cars parked on street"},

    # --- everyday science ---
    {"id": "onions_cry", "category": "science", "prompt": "why cutting onions makes you cry, down to the actual chemistry happening at your eyeball", "image_type": "photo", "photo_keywords": "chopping onions kitchen"},
    {"id": "ice_floats", "category": "science", "prompt": "why ice floats instead of sinking, and why that's actually a weird exception for how most substances behave when they freeze", "image_type": "photo", "photo_keywords": "ice cubes floating water"},
    {"id": "sky_blue", "category": "science", "prompt": "why the sky is blue during the day and orange/red at sunset, same sunlight, different result", "image_type": "photo", "photo_keywords": "blue sky daytime clouds"},
    {"id": "microwave_uneven", "category": "science", "prompt": "why microwaves heat food unevenly, leaving some bites cold and others molten", "image_type": "photo", "photo_keywords": "microwave oven kitchen"},
    {"id": "battery_cold", "category": "science", "prompt": "why phone batteries drain so much faster in cold weather", "image_type": "photo", "photo_keywords": "smartphone winter cold outdoors"},

    # --- history / origin curiosities ---
    {"id": "barcode_vs_qr", "category": "history", "prompt": "the barcode versus the QR code: where each one came from and why QR codes can survive being partly covered or damaged", "image_type": "photo", "photo_keywords": "barcode scanner grocery checkout"},
    {"id": "qwerty", "category": "history", "prompt": "the QWERTY keyboard layout, why it isn't alphabetical, and why it never got replaced once faster layouts existed", "image_type": "photo", "photo_keywords": "computer keyboard closeup"},
    {"id": "y2k", "category": "history", "prompt": "the Y2K bug: why storing years as two digits was a reasonable shortcut for decades until it suddenly wasn't", "image_type": "diagram"},
    {"id": "driving_side", "category": "history", "prompt": "why some countries drive on the left and others on the right, and how that split actually happened", "image_type": "photo", "photo_keywords": "cars driving on road"},

    # --- internet / tech trivia ---
    {"id": "ctrl_z", "category": "trivia", "prompt": "Ctrl+Z (undo) and how software actually keeps track of everything you've done so it can reverse it", "image_type": "photo", "photo_keywords": "keyboard keys closeup"},
    {"id": "deleted_files", "category": "trivia", "prompt": "why a 'deleted' file usually isn't actually gone right away, and what your computer really does when you delete something", "image_type": "diagram"},
    {"id": "banana_problem", "category": "trivia", "prompt": "the 'banana problem' in software dependencies: you wanted a banana, but you got the gorilla holding the banana, and the whole jungle behind it", "image_type": "diagram"},
]

_BY_ID = {t["id"]: t for t in TOPICS}


def pick_next_topic(recent_history: list[dict], exclude_ids: set = frozenset()) -> dict:
    """Pick a topic avoiding: the most recent category, any topic id used
    within the current cycle (resets once every topic in that category has
    been used once), and any id in `exclude_ids` (topics already tried and
    rejected earlier in the SAME run — since this function is otherwise a
    pure function of `recent_history`, calling it again with unchanged
    history would just deterministically return the same topic again).
    `recent_history` is a list of {"topic_id": str, "category": str} ordered
    most-recent-first.

    Rotation happens at the CATEGORY level first (so all five categories
    cycle through, not just whichever two happen to tie-break first), then
    at the topic level within whichever category is chosen.
    """
    all_categories = sorted({t["category"] for t in TOPICS})
    recent_categories_immediate = {h["category"] for h in recent_history[:1]}
    used_ids = {h["topic_id"] for h in recent_history}

    def category_last_used_index(cat):
        for i, h in enumerate(recent_history):
            if h["category"] == cat:
                return i
        return len(recent_history) + 1  # never used recently — most eligible

    def available_in(cat):
        return [t for t in TOPICS if t["category"] == cat and t["id"] not in exclude_ids]

    eligible_categories = [
        c for c in all_categories if c not in recent_categories_immediate and available_in(c)
    ]
    if not eligible_categories:
        eligible_categories = [c for c in all_categories if available_in(c)]
    if not eligible_categories:
        # every single topic has been excluded this run — give up on exclusion
        eligible_categories = all_categories
        exclude_ids = frozenset()

    eligible_categories.sort(key=category_last_used_index, reverse=True)
    chosen_category = eligible_categories[0]

    category_topics = [t for t in TOPICS if t["category"] == chosen_category and t["id"] not in exclude_ids]
    candidates = [t for t in category_topics if t["id"] not in used_ids]
    if not candidates:
        candidates = category_topics  # every topic in this category has cycled — start over

    def topic_last_used_index(topic):
        for i, h in enumerate(recent_history):
            if h["topic_id"] == topic["id"]:
                return i
        return len(recent_history) + 1

    candidates.sort(key=topic_last_used_index, reverse=True)
    return candidates[0]


def get_topic(topic_id: str) -> dict:
    return _BY_ID[topic_id]
