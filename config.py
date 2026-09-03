import os

from dotenv import load_dotenv

import topics

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GENERATION_MODEL = "claude-sonnet-5"
CRITIC_MODEL = "claude-haiku-4-5-20251001"

TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
# App-only OAuth2 credential -- unrelated to the OAuth1 user-context keys
# above (those post as @lyfzaxi10tal; this authenticates the app itself).
# Only used for read endpoints like GET /2/trends/by/woeid.
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

FIRESTORE_PROJECT_ID = os.getenv("FIRESTORE_PROJECT_ID")

# Only needed by manage_schedule.py, filled in once the Cloud Run service
# actually exists (deploy is a separate, later approval step).
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")
SCHEDULER_SERVICE_ACCOUNT_EMAIL = os.getenv("SCHEDULER_SERVICE_ACCOUNT_EMAIL")

MAX_GENERATION_ATTEMPTS = 3

# pick_next_topic()'s no-repeat-within-a-cycle guarantee can only see back as
# far as this window. It must be at least the bank size or a topic can
# legally repeat before the bank has cycled once (review.py's
# check_history_window_vs_bank — a 7-post window against a 54-topic bank
# meant a repeat could happen in under two days). Tied to the bank size with
# 2x headroom, matching test_topics.py's own margin, so this can't silently
# drift out of sync as topics.TOPICS grows or shrinks.
RECENT_HISTORY_WINDOW = len(topics.TOPICS) * 2

# Scheduled slots are hours apart, but two triggers can legitimately land
# minutes apart (a manual trigger near a scheduled time, or a scheduler retry
# racing a slow-but-still-running original request) -- skip posting if the
# last successful post was more recent than this, rather than risk a
# double-post from the same intended slot.
MIN_MINUTES_BETWEEN_POSTS = 20
