"""Image sourcing. Two paths, chosen per-topic (topics.py `image_type`):

- diagram: Claude generates simple SVG, we validate it's well-formed XML, then
  rasterize to PNG with cairosvg. No copyright concern — we author it.
- photo: query Unsplash (falling back to Pexels) for a real photo, explicitly
  checking the license/plan field on every candidate before accepting it —
  never just grabbing the first result blind.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import anthropic
import cairosvg
import requests

import config
from llm_utils import extract_text

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

MEDIA_DIR = "tmp_media"

_DIAGRAM_SYSTEM_PROMPT = """You produce a single simple SVG diagram illustrating a concept for a \
tech/science explainer post. Rules:
- viewBox="0 0 800 500", clean and minimal — a handful of shapes, arrows, and short text labels.
- Use at most 3-4 colors, legible sans-serif text (font-family="sans-serif"), clear contrast.
- No photographic detail, no gradients, no external references, no <script> or <foreignObject>.
- Output ONLY the raw <svg>...</svg> markup, nothing else — no markdown fences, no explanation."""


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


def _generate_diagram_svg(topic: dict) -> str:
    resp = _client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=3000,
        thinking={"type": "disabled"},
        system=_DIAGRAM_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Diagram concept: {topic['prompt']}"}],
    )
    svg = extract_text(resp)
    if svg.startswith("```"):
        svg = svg.strip("`")
        if svg.lower().startswith("svg"):
            svg = svg[3:]
    return svg.strip()


def _make_diagram(topic: dict) -> SourcedImage:
    svg = _generate_diagram_svg(topic)
    try:
        ET.fromstring(svg)
    except ET.ParseError as e:
        raise ImageSourcingError(f"generated SVG is not well-formed: {e}")

    os.makedirs(MEDIA_DIR, exist_ok=True)
    out_path = os.path.join(MEDIA_DIR, f"{topic['id']}_diagram.png")
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=out_path, output_width=800, output_height=500)
    return SourcedImage(path=out_path, source="generated-diagram", attribution="")


def _unsplash_search(keywords: str, subject: str) -> SourcedImage | None:
    if not config.UNSPLASH_ACCESS_KEY:
        return None
    resp = requests.get(
        "https://api.unsplash.com/search/photos",
        headers={"Authorization": f"Client-ID {config.UNSPLASH_ACCESS_KEY}"},
        params={"query": keywords, "per_page": 10, "content_filter": "high"},
        timeout=15,
    )
    resp.raise_for_status()
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

        os.makedirs(MEDIA_DIR, exist_ok=True)
        image_url = photo["urls"]["regular"]
        img_bytes = requests.get(image_url, timeout=15).content
        out_path = os.path.join(MEDIA_DIR, f"unsplash_{photo['id']}.jpg")
        with open(out_path, "wb") as f:
            f.write(img_bytes)

        attribution = f"Unsplash — {photo['user']['name']} ({photo['links']['html']}), standard Unsplash License"
        return SourcedImage(path=out_path, source="unsplash", attribution=attribution)

    return None


def _pexels_search(keywords: str, subject: str) -> SourcedImage | None:
    if not config.PEXELS_API_KEY:
        return None
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": config.PEXELS_API_KEY},
        params={"query": keywords, "per_page": 10},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("photos", [])

    for photo in results:
        # All standard Pexels API results are under the Pexels License (free
        # for use), no separate paid tier to filter out here — but still
        # require the description to actually match the topic's subject.
        if not _matches_subject(photo.get("alt", ""), subject):
            continue

        os.makedirs(MEDIA_DIR, exist_ok=True)
        image_url = photo["src"]["large"]
        img_bytes = requests.get(image_url, timeout=15).content
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
