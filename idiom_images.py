"""
Idiom illustration generation via Gemini (Nano Banana / gemini-2.5-flash-image).

WHY THIS EXISTS SEPARATELY FROM images.py
------------------------------------------
images.py has two paths: self-authored SVG diagrams (mechanism explanations)
or licensed stock photos (subject-matched). Neither fits idiom posts -- a
diagram can't carry a narrative scene, and stock libraries don't have
reenactments of a 1785 flogging or a 1432 Scottish courtroom.

The three pilot images (bite_the_bullet, break_the_ice, caught_red_handed)
were generated manually via Gemini and came back strong once the prompt
locked in "woodcut engraving, cross-hatching, not photorealistic" language.
This module automates that exact prompt shape.

CRITICAL: STYLE, NOT EVIDENCE
------------------------------
These images are atmospheric depictions, not documentary proof -- the same
way a magazine article uses a mood illustration rather than a photograph.
The engraving/woodcut style is not a stylistic preference, it's the thing
that keeps this honest: a photorealistic "vintage photo" of an invented scene
risks being mistaken for a real historical photograph, which this account's
entire credibility depends on never doing. Every prompt below hard-codes
"not photorealistic" and an illustration style. Do not "upgrade" these to
photorealistic renders even if the results look better -- that trade is not
worth making for this account.

SETUP
-----
Requires GEMINI_API_KEY in .env, loaded via config.py exactly like every
other credential in this project (UNSPLASH_ACCESS_KEY, PEXELS_API_KEY, etc).
Never paste the key directly into code, chat, or version control -- .env is
already gitignored per the existing project convention.

    # .env
    GEMINI_API_KEY=your-key-here

    # config.py -- add alongside the other keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
"""
from __future__ import annotations

import base64
import logging
import os
import re

import requests

import config

MEDIA_DIR = "tmp_media"

_MODEL = "gemini-2.5-flash-image"
_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"

# Locked style fragment. Every idiom image prompt is built by wrapping
# idiom_topics.py's `image_style` scene description in this exact template.
# Changing this changes the look of every future idiom image at once --
# keep the whole series visually consistent rather than editing per-post.
_STYLE_TEMPLATE = (
    "Black-and-white {era}-century woodcut engraving style, cross-hatching "
    "linework, not photorealistic, aged paper texture. {scene}. Illustrative "
    "line-art style like an old book engraving, not a photograph."
)


class IdiomImageError(Exception):
    pass


def build_prompt(era: str, scene: str) -> str:
    """
    era: e.g. "18th", "19th", "15th"
    scene: idiom_topics.py's `image_style` field for this idiom
    """
    return _STYLE_TEMPLATE.format(era=era, scene=scene)


def generate_idiom_image(idiom_id: str, era: str, scene: str) -> str:
    """
    Calls Gemini image generation and writes the result to MEDIA_DIR.
    Returns the local file path.

    Raises IdiomImageError on any failure -- caller (app.py-equivalent
    pipeline) should treat this the same way images.ImageSourcingError is
    treated: skip the slot or fall back to a plain text-only post, never let
    it crash the request.
    """
    if not config.GEMINI_API_KEY:
        raise IdiomImageError("GEMINI_API_KEY is not set")

    prompt = build_prompt(era, scene)

    try:
        resp = requests.post(
            _ENDPOINT,
            params={"key": config.GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"]},
            },
            timeout=60,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise IdiomImageError(f"Gemini request failed: {e}")

    data = resp.json()

    try:
        candidates = data["candidates"]
        parts = candidates[0]["content"]["parts"]
        image_part = next(p for p in parts if "inlineData" in p)
        image_b64 = image_part["inlineData"]["data"]
    except (KeyError, IndexError, StopIteration):
        raise IdiomImageError(
            f"Gemini response did not contain an image; response shape: {list(data.keys())}"
        )

    os.makedirs(MEDIA_DIR, exist_ok=True)
    out_path = os.path.join(MEDIA_DIR, f"{idiom_id}_illustration.png")
    try:
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(image_b64))
    except (base64.binascii.Error, OSError) as e:
        raise IdiomImageError(f"failed to decode/write image: {e}")

    logging.info("Generated idiom illustration for '%s' -> %s", idiom_id, out_path)
    return out_path


def generate_for_topic(topic: dict, era: str | None = None) -> str:
    """Convenience wrapper taking an idiom_topics.py entry directly. Era
    comes from the bank entry's `era` field (override via the parameter)."""
    return generate_idiom_image(topic["id"], era or topic.get("era", "19th"), topic["image_style"])


def check_image_relevance(path: str, scene: str) -> tuple[bool, str]:
    """Cheap vision check: does the generated image actually depict the
    bank's scene? Gemini occasionally drifts off-prompt, and an off-topic
    image under a history post costs exactly the credibility this account
    runs on. Uses the Haiku critic model with the image inline (~a tenth of
    a cent per check). Returns (relevant, reason).

    Judged loosely on purpose — an engraving interpretation never matches a
    scene description word for word. Fail only when the image is about
    something else entirely, or contradicts the scene's core elements."""
    import anthropic

    import llm_utils

    with open(path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode("ascii")

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)
    resp = client.messages.create(
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
                    "people/place/action).\n\n"
                    "Reply in EXACTLY this format, nothing else:\n"
                    "RELEVANT: YES or NO\n"
                    "REASON: one short sentence"
                )},
            ],
        }],
    )
    text = llm_utils.extract_text(resp)
    relevant = bool(re.search(r"RELEVANT:\s*YES", text, re.IGNORECASE))
    reason_match = re.search(r"REASON:\s*(.*)", text, re.IGNORECASE)
    reason = reason_match.group(1).strip() if reason_match else text[:200]
    return relevant, reason


if __name__ == "__main__":
    # Manual smoke test -- does NOT run automatically, requires a real key.
    # Usage: python idiom_images.py
    import sys

    sys.path.insert(0, ".")
    from idiom_topics import IDIOM_TOPICS

    # Full-bank smoke tests cost one Gemini image per idiom -- pass ids to
    # test specific entries, or --first-3 for a quick spot check.
    ids = [a for a in sys.argv[1:] if not a.startswith("-")]
    to_test = [t for t in IDIOM_TOPICS if not ids or t["id"] in ids]
    if "--first-3" in sys.argv:
        to_test = to_test[:3]

    for topic in to_test:
        try:
            path = generate_for_topic(topic)
            relevant, reason = check_image_relevance(path, topic["image_style"])
            print(f"OK  {topic['id']} -> {path}  relevance={'PASS' if relevant else 'FAIL'} ({reason})")
        except IdiomImageError as e:
            print(f"FAIL {topic['id']}: {e}")
