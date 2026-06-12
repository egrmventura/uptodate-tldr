"""LLM summarization: turns ranked items into a persona-tuned TL;DR digest.

The persona (voice/tone) lives entirely in the system prompt and is sourced
from config.yaml `persona.prompt` (overridable via the `PERSONA_PROMPT` env
var, see config.py). This keeps "how the digest sounds" decoupled from "how
the digest is generated" — swapping personas is a config change, not a
prompt-engineering change to this module.
"""

from __future__ import annotations

import os
from typing import Any

import anthropic

from sources.base import Item

_USER_PROMPT_TEMPLATE = """\
Write a TL;DR digest of today's top {count} items on the topic "{topic}".

For each item, write one tight paragraph that includes:
- A short headline (bold)
- The core insight or claim
- Why it matters

Here are the items, with their source, title, URL, and a raw excerpt:

{items_block}

Output the digest as Markdown, with each item as its own paragraph. Do not
add a preamble or closing remarks — start directly with the first item.
"""


def _format_item(index: int, item: Item) -> str:
    return (
        f"{index}. [{item.source}] {item.title}\n"
        f"   URL: {item.url}\n"
        f"   Excerpt: {item.summary_raw or '(no excerpt available)'}"
    )


def build_user_prompt(items: list[Item], topic: str) -> str:
    items_block = "\n".join(_format_item(i + 1, item) for i, item in enumerate(items))
    return _USER_PROMPT_TEMPLATE.format(count=len(items), topic=topic, items_block=items_block)


def summarize(items: list[Item], config: dict[str, Any]) -> str:
    """Call the Anthropic API to produce the digest markdown body.

    Raises if the API call fails — summarization failure should abort the
    run (there's nothing useful to deliver), unlike a single source
    failing during ingestion.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    persona_prompt = config["persona"]["prompt"]
    llm_config = config.get("llm", {})
    model = llm_config.get("model", "claude-sonnet-4-6")
    max_tokens = llm_config.get("max_tokens", 2000)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=persona_prompt,
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(items, config["topic"]),
            }
        ],
    )

    return "".join(block.text for block in response.content if block.type == "text")
