import os

from dotenv import load_dotenv

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

# How much post history run_pipeline() pulls for recent_openings (opening-
# line repetition avoidance) and the duplicate-post-time guard. No longer
# tied to a topic bank's size (there isn't one) -- topic_generate.py's own
# DIGEST_LIMIT governs how much history the novelty check itself considers.
RECENT_HISTORY_WINDOW = 120

# Scheduled slots are hours apart, but two triggers can legitimately land
# minutes apart (a manual trigger near a scheduled time, or a scheduler retry
# racing a slow-but-still-running original request) -- skip posting if the
# last successful post was more recent than this, rather than risk a
# double-post from the same intended slot.
MIN_MINUTES_BETWEEN_POSTS = 20
