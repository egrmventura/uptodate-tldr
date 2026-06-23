"""Configuration loading: merges config.yaml with environment variable overrides.

Supported env var overrides: TOPIC, TOP_N, PERSONA_PROMPT (see _ENV_OVERRIDES).
Add new entries to _ENV_OVERRIDES to make additional config keys overridable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

# Maps env var names to the (possibly nested) config key they override.
_ENV_OVERRIDES: dict[str, tuple[str, ...]] = {
    "TOPIC": ("topic",),
    "TOP_N": ("top_n",),
    "PERSONA_PROMPT": ("persona", "prompt"),
}


def _set_nested(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = data
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value


def load_config() -> dict[str, Any]:
    """Load config.yaml and apply environment variable overrides."""
    with open(CONFIG_PATH, "r") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    for env_var, path in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None:
            continue
        if path == ("top_n",):
            _set_nested(config, path, int(raw))
        else:
            _set_nested(config, path, raw)

    return config
