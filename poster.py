"""Posting to X. Media upload still requires the v1.1 tweepy.API (media_upload
has no v2 equivalent), but tweet creation itself must go through the v2
tweepy.Client — X retired the v1.1 statuses/update endpoint (confirmed via a
live 404 from api.update_status during testing). Both use the same OAuth1
user-context credentials.
"""
from __future__ import annotations

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


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=config.TWITTER_API_KEY,
        consumer_secret=config.TWITTER_API_SECRET,
        access_token=config.TWITTER_ACCESS_TOKEN,
        access_token_secret=config.TWITTER_ACCESS_TOKEN_SECRET,
    )


def post(text: str, image_path: str | None) -> str:
    """Posts the given text, with one attached image when image_path is set,
    text-only when it's None (idiom posts ship text-only if Gemini image
    generation fails, rather than skipping the slot). Returns the tweet id."""
    media_ids = None
    if image_path:
        media = _get_api().media_upload(image_path)
        media_ids = [media.media_id]
    response = _get_client().create_tweet(text=text, media_ids=media_ids)
    return str(response.data["id"])
