"""Draft generation via Claude. One call per post, few-shot'd on the
user-approved example voice."""
import anthropic

import config
from generate_prompt import SYSTEM_PROMPT, build_user_turn
from llm_utils import extract_text

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3)


def generate_draft(topic: dict, recent_openings: list[str], retry_hint: str = "") -> str:
    user_turn = build_user_turn(topic, recent_openings) + retry_hint

    resp = _client.messages.create(
        model=config.GENERATION_MODEL,
        max_tokens=1500,
        thinking={"type": "disabled"},
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_turn}],
    )
    return extract_text(resp)
