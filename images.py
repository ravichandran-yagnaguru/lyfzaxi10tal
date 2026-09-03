"""Image sourcing. Two paths, chosen per-topic (topics.py `image_type`):

- diagram: Gemini (Nano Banana / gemini-2.5-flash-image) generates an
  illustrated scene of the topic's universal_door in a clean, modern,
  non-photorealistic style, then a Haiku vision check confirms it actually
  depicts the intended scene before it's used.
- photo: query Unsplash (falling back to Pexels) for a real photo, explicitly
  checking the license/plan field on every candidate before accepting it —
  never just grabbing the first result blind.

WHY THE DIAGRAM PATH CHANGED FROM SELF-AUTHORED SVG
----------------------------------------------------
The original diagram path had Claude write raw SVG (shapes/arrows/labels),
rasterized with cairosvg. It was safe (self-authored, no license risk) but
visually thin — Guru's direct feedback was that these images "don't look
good." Gemini's illustration quality is already proven on the idiom format's
engravings, so the diagram path now uses the same engine, with its own
locked style (distinct from idiom's historical woodcuts — this is a clean
modern illustration style suited to science/psychology/everyday-life scenes,
not historical narrative) plus the same vision-relevance gate idiom_images.py
uses, since an off-topic illustration is exactly the kind of thing that costs
this account credibility.

This is a self-contained, parallel implementation rather than an import from
idiom_images.py, matching this project's established pattern of keeping each
format's pipeline independently editable (see idiom_images.py's own
docstring) — a change here can never regress the already-verified idiom path.
"""
from __future__ import annotations

import base64
import logging
import os
import re
from dataclasses import dataclass

import anthropic
import requests

import config
from llm_utils import extract_text

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)

MEDIA_DIR = "tmp_media"

_GEMINI_MODEL = "gemini-2.5-flash-image"
_GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL}:generateContent"

# Locked style — every diagram-type image wraps the topic's universal_door
# (already written as a concrete, drawable lived moment by schema design) in
# this exact template. Changing this changes every future diagram image's
# look at once; keep the series visually consistent rather than editing
# per-post. Deliberately distinct from idiom_images.py's historical-engraving
# style — this is present-day, editorial, not narrative-history.
_DIAGRAM_STYLE_TEMPLATE = (
    "Clean modern flat digital illustration, soft muted color palette, simple "
    "bold shapes, gentle soft shadows, minimal linework, no text or labels "
    "anywhere in the image, not photorealistic, in the style of a "
    "contemporary editorial science-explainer illustration. Scene: {scene}"
)

# Two attempts total: one regeneration if the first image fails the vision
# relevance check, matching idiom_images.py's proven pattern.
_MAX_DIAGRAM_ATTEMPTS = 2


@dataclass
class SourcedImage:
    path: str
    source: str  # "generated-diagram" | "unsplash" | "pexels"
    attribution: str  # empty for diagrams


class ImageSourcingError(Exception):
    pass


def _matches_subject(text: str, subject: str) -> bool:
    """Search APIs are fuzzy/semantic — the top license-compliant result is
    often thematically unrelated (e.g. a generic 'chopping vegetables' photo
    for a search about onions specifically; generic words in the search query
    like 'kitchen' match almost anything, so matching against the whole
    keyword bag isn't reliable). Instead require the photo's own description
    to actually mention the topic's specific subject noun, with basic
    singular/plural handling since Unsplash/Pexels descriptions don't always
    match the query's exact word form."""
    if not text or not subject:
        return False
    text_lower = text.lower()
    subject_lower = subject.lower()
    variant = subject_lower[:-1] if subject_lower.endswith("s") else subject_lower + "s"
    return subject_lower in text_lower or variant in text_lower


def _generate_gemini_illustration(topic_id: str, scene: str) -> str:
    """Calls Gemini image generation, writes the PNG to MEDIA_DIR, returns the
    local file path. Raises ImageSourcingError on any failure — same
    treatment as every other failure mode in this module."""
    if not config.GEMINI_API_KEY:
        raise ImageSourcingError("GEMINI_API_KEY is not set")

    prompt = _DIAGRAM_STYLE_TEMPLATE.format(scene=scene)
    try:
        resp = requests.post(
            _GEMINI_ENDPOINT,
            params={"key": config.GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"]},
            },
            timeout=60,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise ImageSourcingError(f"Gemini request failed: {e}")

    data = resp.json()
    try:
        candidates = data["candidates"]
        parts = candidates[0]["content"]["parts"]
        image_part = next(p for p in parts if "inlineData" in p)
        image_b64 = image_part["inlineData"]["data"]
    except (KeyError, IndexError, StopIteration):
        raise ImageSourcingError(
            f"Gemini response did not contain an image; response shape: {list(data.keys())}"
        )

    os.makedirs(MEDIA_DIR, exist_ok=True)
    out_path = os.path.join(MEDIA_DIR, f"{topic_id}_illustration.png")
    try:
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(image_b64))
    except (base64.binascii.Error, OSError) as e:
        raise ImageSourcingError(f"failed to decode/write image: {e}")

    return out_path


def _check_illustration_relevance(path: str, scene: str) -> tuple[bool, str]:
    """Cheap vision check: does the generated illustration actually depict
    the intended scene? Gemini occasionally drifts off-prompt. Judged loosely
    on purpose — an illustration interpretation never matches word for word;
    fail only when it's clearly about something else or contradicts the
    scene's core subject."""
    with open(path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode("ascii")

    resp = _client.messages.create(
        model=config.CRITIC_MODEL,
        max_tokens=300,
        thinking={"type": "disabled"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_b64}},
                {"type": "text", "text": (
                    "This illustration was generated for the following scene description:\n\n"
                    f"{scene}\n\n"
                    "Does the image broadly depict this scene? Judge loosely — artistic "
                    "interpretation, missing minor details, and extra background elements "
                    "are all fine. Answer NO only if the image shows something else "
                    "entirely or contradicts the scene's core subject (wrong kind of "
                    "person/object/action).\n\n"
                    "Reply in EXACTLY this format, nothing else:\n"
                    "RELEVANT: YES or NO\n"
                    "REASON: one short sentence"
                )},
            ],
        }],
    )
    text = extract_text(resp)
    relevant = bool(re.search(r"RELEVANT:\s*YES", text, re.IGNORECASE))
    reason_match = re.search(r"REASON:\s*(.*)", text, re.IGNORECASE)
    reason = reason_match.group(1).strip() if reason_match else text[:200]
    return relevant, reason


def _make_diagram(topic: dict) -> SourcedImage:
    scene = topic.get("universal_door") or topic["prompt"]
    last_reason = ""
    for _ in range(_MAX_DIAGRAM_ATTEMPTS):
        path = _generate_gemini_illustration(topic["id"], scene)
        relevant, reason = _check_illustration_relevance(path, scene)
        if relevant:
            return SourcedImage(path=path, source="gemini-illustration", attribution="")
        last_reason = reason
    raise ImageSourcingError(f"generated illustration failed relevance check twice: {last_reason}")


def _unsplash_search(keywords: str, subject: str) -> SourcedImage | None:
    if not config.UNSPLASH_ACCESS_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            headers={"Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}"},
            params={"query": keywords, "per_page": 10, "content_filter": "high"},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.warning("Unsplash search failed, falling back: %s", e)
        return None
    results = resp.json().get("results", [])

    for photo in results:
        # Standard Unsplash API search never returns Unsplash+ exclusive
        # content, but we still check explicitly rather than trusting that —
        # `plus`/`premium` style flags, if present, mean "not free license".
        is_plus = photo.get("plus", False) or photo.get("premium", False)
        if is_plus:
            continue

        description = " ".join(filter(None, [photo.get("alt_description"), photo.get("description")]))
        if not _matches_subject(description, subject):
            continue

        image_url = photo["urls"]["regular"]
        try:
            resp = requests.get(image_url, timeout=15)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.warning("Unsplash image download failed, trying next candidate: %s", e)
            continue
        img_bytes = resp.content

        os.makedirs(MEDIA_DIR, exist_ok=True)
        out_path = os.path.join(MEDIA_DIR, f"unsplash_{photo['id']}.jpg")
        with open(out_path, "wb") as f:
            f.write(img_bytes)

        attribution = f"Unsplash — {photo['user']['name']} ({photo['links']['html']}), standard Unsplash License"
        return SourcedImage(path=out_path, source="unsplash", attribution=attribution)

    return None


def _pexels_search(keywords: str, subject: str) -> SourcedImage | None:
    if not config.PEXELS_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": keywords, "per_page": 10},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.warning("Pexels search failed: %s", e)
        return None
    results = resp.json().get("photos", [])

    for photo in results:
        # All standard Pexels API results are under the Pexels License (free
        # for use), no separate paid tier to filter out here — but still
        # require the description to actually match the topic's subject.
        if not _matches_subject(photo.get("alt", ""), subject):
            continue

        image_url = photo["src"]["large"]
        try:
            resp = requests.get(image_url, timeout=15)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.warning("Pexels image download failed, trying next candidate: %s", e)
            continue
        img_bytes = resp.content

        os.makedirs(MEDIA_DIR, exist_ok=True)
        out_path = os.path.join(MEDIA_DIR, f"pexels_{photo['id']}.jpg")
        with open(out_path, "wb") as f:
            f.write(img_bytes)

        attribution = f"Pexels — {photo['photographer']} ({photo['url']}), Pexels License"
        return SourcedImage(path=out_path, source="pexels", attribution=attribution)

    return None


def source_image(topic: dict) -> SourcedImage:
    if topic["image_type"] == "diagram":
        return _make_diagram(topic)

    keywords = topic.get("photo_keywords", topic["prompt"])
    subject = topic["photo_subject"]
    image = _unsplash_search(keywords, subject) or _pexels_search(keywords, subject)
    if image is None:
        raise ImageSourcingError(
            f"no free-license photo matching subject {subject!r} found for keywords: {keywords!r}"
        )
    return image
