"""Posting to X. Reuses the OAuth1 + v1.1 media-upload pattern from the old
repo (that part was sound) — tweepy.API is still required for media uploads,
long-form text posting works the same way once the account has Premium.
"""
import tweepy

import config


def _get_api() -> tweepy.API:
    auth = tweepy.OAuth1UserHandler(
        consumer_key=config.TWITTER_API_KEY,
        consumer_secret=config.TWITTER_API_SECRET,
        access_token=config.TWITTER_ACCESS_TOKEN,
        access_token_secret=config.TWITTER_ACCESS_TOKEN_SECRET,
    )
    return tweepy.API(auth)


def post(text: str, image_path: str) -> str:
    """Posts the given text with one attached image. Returns the tweet id."""
    api = _get_api()
    media = api.media_upload(image_path)
    status = api.update_status(status=text, media_ids=[media.media_id])
    return str(status.id)
