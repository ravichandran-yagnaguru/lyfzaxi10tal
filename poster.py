"""Posting to X. Media upload still requires the v1.1 tweepy.API (media_upload
has no v2 equivalent), but tweet creation itself must go through the v2
tweepy.Client — X retired the v1.1 statuses/update endpoint (confirmed via a
live 404 from api.update_status during testing). Both use the same OAuth1
user-context credentials.
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


def _get_client() -> tweepy.Client:
    return tweepy.Client(
        consumer_key=config.TWITTER_API_KEY,
        consumer_secret=config.TWITTER_API_SECRET,
        access_token=config.TWITTER_ACCESS_TOKEN,
        access_token_secret=config.TWITTER_ACCESS_TOKEN_SECRET,
    )


def post(text: str, image_path: str) -> str:
    """Posts the given text with one attached image. Returns the tweet id."""
    media = _get_api().media_upload(image_path)
    response = _get_client().create_tweet(text=text, media_ids=[media.media_id])
    return str(response.data["id"])
