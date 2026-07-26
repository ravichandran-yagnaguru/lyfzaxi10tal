"""Shared helper for reading Claude API responses. Content blocks can include
thinking blocks ahead of the actual text block — never assume content[0] is
the text.
"""


def extract_text(response) -> str:
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "".join(parts).strip()
