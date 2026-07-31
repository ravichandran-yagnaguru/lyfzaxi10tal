"""Topic bank + selection logic. Selection reads recent post history (passed in
from state.py) so it can avoid repeating a category back-to-back and avoid
reusing a topic until the bank cycles.
"""
import random

TOPICS = [
    # --- technology ---
    {"id": "cfs_scheduler", "category": "tech", "prompt": "the Linux CFS (Completely Fair Scheduler) and how it decides which process runs next", "image_type": "diagram"},
    {"id": "keda", "category": "tech", "prompt": "KEDA (Kubernetes Event-Driven Autoscaling) and how it scales workloads based on event/queue depth instead of just CPU", "image_type": "diagram"},
    {"id": "ocr", "category": "tech", "prompt": "OCR (optical character recognition) and how software turns a photo of text into actual editable text", "image_type": "photo", "photo_keywords": "scanning document text closeup", "photo_subject": "document"},
    {"id": "iac", "category": "tech", "prompt": "infrastructure as code (IaC) and why teams describe servers/cloud resources in text files instead of clicking through a console", "image_type": "diagram"},
    {"id": "backpressure", "category": "tech", "prompt": "backpressure in software systems, and what happens when a fast producer overwhelms a slow consumer", "image_type": "diagram"},
    {"id": "circuit_breaker", "category": "tech", "prompt": "the circuit breaker pattern in distributed systems and how it stops one failing service from taking down everything else", "image_type": "diagram"},
    {"id": "indexing", "category": "tech", "prompt": "database indexing and why looking something up by an indexed column is so much faster than a full table scan", "image_type": "photo", "photo_keywords": "book index pages", "photo_subject": "index"},
    {"id": "partitioning", "category": "tech", "prompt": "database partitioning and how splitting one huge table into smaller chunks speeds things up", "image_type": "diagram"},
    {"id": "sharding", "category": "tech", "prompt": "database sharding and how it spreads data across multiple machines instead of one", "image_type": "diagram"},
    {"id": "rag", "category": "tech", "prompt": "RAG (retrieval-augmented generation) and how it lets an AI model answer using documents it was never trained on", "image_type": "diagram"},
    {"id": "embeddings", "category": "tech", "prompt": "embeddings and how turning words into lists of numbers lets computers tell that 'dog' and 'puppy' are related", "image_type": "diagram"},
    {"id": "cdn", "category": "tech", "prompt": "CDNs (content delivery networks) and why a video loads faster when a copy is sitting physically closer to you", "image_type": "diagram"},
    {"id": "idempotency", "category": "tech", "prompt": "idempotency in APIs and why retrying a request safely shouldn't double-charge or double-create anything", "image_type": "diagram"},
    {"id": "cgroups", "category": "tech", "prompt": "Linux cgroups and how they let the OS put a hard limit on how much CPU/memory one process is allowed to hog", "image_type": "diagram"},
    {"id": "ctrl_z", "category": "tech", "prompt": "Ctrl+Z (undo) and how software actually keeps track of everything you've done so it can reverse it", "image_type": "photo", "photo_keywords": "keyboard keys closeup", "photo_subject": "keyboard"},
    {"id": "deleted_files", "category": "tech", "prompt": "why a 'deleted' file usually isn't actually gone right away, and what your computer really does when you delete something", "image_type": "diagram"},
    {"id": "banana_problem", "category": "tech", "prompt": "the 'banana problem' in software dependencies: you wanted a banana, but you got the gorilla holding the banana, and the whole jungle behind it", "image_type": "diagram"},

    # --- psychology ---
    {"id": "zeigarnik", "category": "psychology", "prompt": "the Zeigarnik effect: why unfinished tasks nag at your memory way more than finished ones", "image_type": "diagram"},
    {"id": "dunning_kruger", "category": "psychology", "prompt": "the Dunning-Kruger effect and why people with the least skill in something are often the most confident about it", "image_type": "diagram"},
    {"id": "placebo_effect", "category": "psychology", "prompt": "the placebo effect and how a fake treatment with no active ingredient can still measurably help people feel better", "image_type": "photo", "photo_keywords": "white pills bottle", "photo_subject": "pill"},
    {"id": "bystander_effect", "category": "psychology", "prompt": "the bystander effect and why someone is less likely to help in an emergency the more other people are standing around", "image_type": "photo", "photo_keywords": "crowd of people city street", "photo_subject": "crowd"},
    {"id": "baader_meinhof", "category": "psychology", "prompt": "the Baader-Meinhof phenomenon (frequency illusion): why you suddenly start noticing something everywhere right after you first learn about it", "image_type": "photo", "photo_keywords": "cars parked on street", "photo_subject": "car"},
    {"id": "deja_vu", "category": "psychology", "prompt": "deja vu: what neuroscience actually knows (and doesn't) about why a brand-new moment can feel like a repeat", "image_type": "diagram"},
    {"id": "mandela_effect", "category": "psychology", "prompt": "the Mandela effect: why large numbers of unrelated people can confidently share the exact same false memory", "image_type": "diagram"},
    {"id": "time_speeds_up", "category": "psychology", "prompt": "why time feels like it speeds up as you get older, and the actual perception theories behind it", "image_type": "diagram"},
    {"id": "cant_tickle_self", "category": "psychology", "prompt": "why you can't tickle yourself: the brain's own prediction system canceling out the sensation", "image_type": "diagram"},
    {"id": "dunbar_number", "category": "psychology", "prompt": "the Dunbar number: the cognitive cap on how many stable relationships a person's brain can realistically maintain", "image_type": "diagram"},

    # --- everyday science ---
    {"id": "onions_cry", "category": "science", "prompt": "why cutting onions makes you cry, down to the actual chemistry happening at your eyeball", "image_type": "photo", "photo_keywords": "sliced onion cutting board kitchen", "photo_subject": "onion"},
    {"id": "ice_floats", "category": "science", "prompt": "why ice floats instead of sinking, and why that's actually a weird exception for how most substances behave when they freeze", "image_type": "photo", "photo_keywords": "ice cubes floating water", "photo_subject": "ice"},
    {"id": "sky_blue", "category": "science", "prompt": "why the sky is blue during the day and orange/red at sunset, same sunlight, different result", "image_type": "photo", "photo_keywords": "blue sky daytime clouds", "photo_subject": "sky"},
    {"id": "microwave_uneven", "category": "science", "prompt": "why microwaves heat food unevenly, leaving some bites cold and others molten", "image_type": "photo", "photo_keywords": "microwave oven kitchen", "photo_subject": "microwave"},
    {"id": "battery_cold", "category": "science", "prompt": "why phone batteries drain so much faster in cold weather", "image_type": "photo", "photo_keywords": "smartphone winter cold outdoors", "photo_subject": "phone"},
    {"id": "goosebumps", "category": "science", "prompt": "goosebumps: the evolutionary leftover reflex from a coat of fur we no longer have", "image_type": "diagram"},
    {"id": "fireworks_colors", "category": "science", "prompt": "why fireworks come in so many different colors: the metal salts and chemistry behind each hue", "image_type": "photo", "photo_keywords": "colorful fireworks night sky", "photo_subject": "fireworks"},

    # --- history / origin curiosities ---
    {"id": "barcode_vs_qr", "category": "history", "prompt": "the barcode versus the QR code: where each one came from and why QR codes can survive being partly covered or damaged", "image_type": "photo", "photo_keywords": "barcode scanner grocery checkout", "photo_subject": "barcode"},
    {"id": "qwerty", "category": "history", "prompt": "the QWERTY keyboard layout, why it isn't alphabetical, and why it never got replaced once faster layouts existed", "image_type": "photo", "photo_keywords": "computer keyboard closeup", "photo_subject": "keyboard"},
    {"id": "y2k", "category": "history", "prompt": "the Y2K bug: why storing years as two digits was a reasonable shortcut for decades until it suddenly wasn't", "image_type": "diagram"},
    {"id": "driving_side", "category": "history", "prompt": "why some countries drive on the left and others on the right, and how that split actually happened", "image_type": "photo", "photo_keywords": "cars driving on road", "photo_subject": "car"},
    {"id": "daylight_saving", "category": "history", "prompt": "daylight saving time: why it started, and why it has survived despite most people disliking it", "image_type": "diagram"},
    {"id": "april_fools", "category": "history", "prompt": "the disputed origin of April Fools' Day, and why nobody can fully agree on how it started", "image_type": "diagram"},
    {"id": "emu_war", "category": "history", "prompt": "the Great Emu War of 1932: Australia's real, actual military campaign against emus, and how it went", "image_type": "diagram"},

    # --- health & the human body ---
    {"id": "hiccups", "category": "health", "prompt": "why we hiccup, and why such a small reflex is so notoriously hard to stop on command", "image_type": "diagram"},
    {"id": "yawning_contagious", "category": "health", "prompt": "why yawning is contagious, and what that has to do with empathy and social bonding", "image_type": "diagram"},
    {"id": "brain_freeze", "category": "health", "prompt": "brain freeze: why eating something cold too fast can cause sudden head pain", "image_type": "photo", "photo_keywords": "person eating ice cream", "photo_subject": "ice cream"},
    {"id": "why_we_blush", "category": "health", "prompt": "why we blush, the one involuntary human expression that's basically impossible to fake or suppress", "image_type": "diagram"},
    {"id": "muscle_soreness", "category": "health", "prompt": "why your muscles get sore a day or two after a hard workout, not right away", "image_type": "diagram"},

    # --- space & astronomy ---
    {"id": "olbers_paradox", "category": "space", "prompt": "Olbers' paradox: if the universe has countless stars, why is the night sky dark instead of blazing white", "image_type": "diagram"},
    {"id": "moon_illusion", "category": "space", "prompt": "the moon illusion: why the moon looks dramatically bigger near the horizon than high in the sky, even though it isn't", "image_type": "photo", "photo_keywords": "full moon night sky", "photo_subject": "moon"},
    {"id": "black_holes", "category": "space", "prompt": "what a black hole actually is in plain terms, without the sci-fi mystique", "image_type": "diagram"},
    {"id": "why_stars_twinkle", "category": "space", "prompt": "why stars twinkle but planets don't, when you look up at the night sky", "image_type": "diagram"},
    {"id": "tides", "category": "space", "prompt": "how the moon's gravity pulls ocean tides in and out twice a day", "image_type": "diagram"},

    # --- food & culture ---
    {"id": "bread_rises", "category": "food", "prompt": "why bread dough rises: the yeast fermentation and gluten science behind it", "image_type": "photo", "photo_keywords": "bread dough baking kitchen", "photo_subject": "bread"},
    {"id": "coffee_trade_history", "category": "food", "prompt": "how the coffee trade shaped world history, from a herder's legend to a global economy", "image_type": "photo", "photo_keywords": "coffee beans roasted", "photo_subject": "coffee"},
    {"id": "why_spicy_burns", "category": "food", "prompt": "why spicy food actually 'burns': capsaicin tricking the same pain receptors that detect real heat", "image_type": "photo", "photo_keywords": "chili peppers closeup", "photo_subject": "chili"},
    {"id": "airplane_food_taste", "category": "food", "prompt": "why airplane food tastes bland: how cabin pressure and dry air dull your taste buds mid-flight", "image_type": "diagram"},

    # --- culture & traditions (historical/comparative, never doctrinal) ---
    {"id": "flood_myths", "category": "culture", "prompt": "why so many unrelated cultures across history have their own version of a great-flood myth, looked at as comparative history, not as a claim about which is true", "image_type": "diagram"},
    {"id": "fasting_traditions", "category": "culture", "prompt": "the history behind fasting traditions across different cultures and calendars, told purely as historical/comparative fact, not doctrine", "image_type": "diagram"},
    {"id": "lunar_vs_solar_calendars", "category": "culture", "prompt": "why lunar and solar calendars drift apart, and why that's the reason some holidays 'move' every year while others don't", "image_type": "diagram"},
    {"id": "new_years_traditions", "category": "culture", "prompt": "how different cultures and calendars around the world mark the start of a new year", "image_type": "photo", "photo_keywords": "new year celebration fireworks crowd", "photo_subject": "fireworks"},
    {"id": "why_rituals_exist", "category": "culture", "prompt": "the psychological function of ritual: why humans across virtually every culture perform repeated symbolic actions", "image_type": "diagram"},

    # --- animals & nature ---
    {"id": "cats_purr", "category": "animals", "prompt": "why cats purr, a behavior that's still not fully explained by science", "image_type": "photo", "photo_keywords": "cat purring closeup", "photo_subject": "cat"},
    {"id": "animal_migration", "category": "animals", "prompt": "how animals like birds and whales navigate thousands of miles without getting lost", "image_type": "photo", "photo_keywords": "birds flying migration formation", "photo_subject": "bird"},
    {"id": "dogs_tilt_heads", "category": "animals", "prompt": "why dogs tilt their heads when you talk to them", "image_type": "photo", "photo_keywords": "dog tilting head", "photo_subject": "dog"},
    {"id": "bioluminescence", "category": "animals", "prompt": "bioluminescence: how and why some creatures generate their own light", "image_type": "photo", "photo_keywords": "jellyfish glowing ocean", "photo_subject": "jellyfish"},
    {"id": "zebra_stripes", "category": "animals", "prompt": "why zebras have stripes: the leading scientific theories, and why the debate isn't fully settled", "image_type": "photo", "photo_keywords": "zebra stripes closeup", "photo_subject": "zebra"},

    # --- money & everyday economics ---
    {"id": "charm_pricing", "category": "money", "prompt": "charm pricing: why $9.99 feels so much cheaper than $10, even though the difference is a single cent", "image_type": "diagram"},
    {"id": "how_inflation_works", "category": "money", "prompt": "how inflation actually works, in plain terms, without the jargon", "image_type": "diagram"},
    {"id": "airline_dynamic_pricing", "category": "money", "prompt": "why airline ticket prices swing so much for the same seat, sometimes within the same hour", "image_type": "diagram"},
    {"id": "opportunity_cost", "category": "money", "prompt": "opportunity cost: the hidden cost of whatever you didn't choose, and why it's easy to ignore", "image_type": "diagram"},
    {"id": "credit_scores", "category": "money", "prompt": "where credit scores came from and what they're actually measuring", "image_type": "diagram"},

    # --- language & words ---
    {"id": "ok_origin", "category": "language", "prompt": "the surprisingly disputed origin of 'OK', and how it became one of the most universally understood words on Earth", "image_type": "diagram"},
    {"id": "loanwords", "category": "language", "prompt": "loanwords: how words like 'kindergarten' or 'pajamas' cross from one language into another and just stay", "image_type": "diagram"},
    {"id": "untranslatable_words", "category": "language", "prompt": "words that exist in some languages with no direct English equivalent, and what that says about how language shapes thought", "image_type": "diagram"},
    {"id": "english_spelling_mess", "category": "language", "prompt": "why English spelling is so inconsistent, a side effect of borrowing words from dozens of other languages over centuries", "image_type": "diagram"},
    {"id": "false_friends", "category": "language", "prompt": "'false friends': words that look nearly identical across two languages but mean something completely different", "image_type": "diagram"},

    # --- sports ---
    {"id": "offside_rule", "category": "sports", "prompt": "why soccer's offside rule exists, and what problem it was actually designed to solve", "image_type": "diagram"},
    {"id": "curveball_physics", "category": "sports", "prompt": "the physics of a curveball: how spinning a ball makes it bend through the air", "image_type": "diagram"},
    {"id": "tennis_tiebreak", "category": "sports", "prompt": "why the tennis tiebreak was invented, and the endless matches it was created to prevent", "image_type": "diagram"},
    {"id": "choking_under_pressure", "category": "sports", "prompt": "the psychology of 'choking' under pressure: why skilled athletes sometimes fail at the exact moment it matters most", "image_type": "diagram"},
    {"id": "marathon_distance", "category": "sports", "prompt": "why a marathon is exactly 26.2 miles, an oddly specific number with a surprisingly royal backstory", "image_type": "diagram"},

    # --- movies & entertainment ---
    {"id": "why_24fps", "category": "movies", "prompt": "why movies settled on 24 frames per second, a technical decision from decades ago that stuck", "image_type": "diagram"},
    {"id": "foley_sound", "category": "movies", "prompt": "foley sound: how fake, hand-made sound effects end up sounding more realistic than the real thing", "image_type": "diagram"},
    {"id": "laugh_track_history", "category": "movies", "prompt": "the history of the sitcom laugh track, and the psychology of why it actually makes things feel funnier", "image_type": "diagram"},
    {"id": "green_screen", "category": "movies", "prompt": "how green screen compositing actually works, and why the color green specifically was chosen", "image_type": "diagram"},

    # --- music ---
    {"id": "minor_key_sadness", "category": "music", "prompt": "why songs in a minor key sound sad, the music theory behind an emotion most people can hear but not explain", "image_type": "diagram"},
    {"id": "earworms", "category": "music", "prompt": "earworms: why certain songs get stuck on repeat in your head for hours", "image_type": "diagram"},
    {"id": "music_chills", "category": "music", "prompt": "why some music gives people literal chills or goosebumps, a neuroscience phenomenon called frisson", "image_type": "diagram"},
    {"id": "autotune_history", "category": "music", "prompt": "how autotune went from an invisible pitch-correction tool to a deliberate, recognizable sound of its own", "image_type": "diagram"},
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

    Rotation happens at the CATEGORY level first (so all categories cycle
    through evenly, not just whichever two happen to tie-break first), then
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

    # Pick randomly among whichever categories are tied for "least recently
    # used" — with an empty or symmetric history every category ties, and a
    # stable sort would deterministically favor the same one (alphabetically
    # first) every single time history is empty, e.g. every fresh deploy.
    best_recency = max(category_last_used_index(c) for c in eligible_categories)
    chosen_category = random.choice([c for c in eligible_categories if category_last_used_index(c) == best_recency])

    category_topics = [t for t in TOPICS if t["category"] == chosen_category and t["id"] not in exclude_ids]
    candidates = [t for t in category_topics if t["id"] not in used_ids]
    if not candidates:
        candidates = category_topics  # every topic in this category has cycled — start over

    def topic_last_used_index(topic):
        for i, h in enumerate(recent_history):
            if h["topic_id"] == topic["id"]:
                return i
        return len(recent_history) + 1

    # Same tie-breaking fix at the topic level.
    best_topic_recency = max(topic_last_used_index(t) for t in candidates)
    tied = [t for t in candidates if topic_last_used_index(t) == best_topic_recency]
    return random.choice(tied)


def get_topic(topic_id: str) -> dict:
    return _BY_ID[topic_id]
