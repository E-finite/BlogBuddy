"""Helpers for loading and rendering prompt templates from prompts/*.txt."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Any


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@lru_cache(maxsize=64)
def load_prompt_template(filename: str) -> str:
    """Load a prompt template by filename from the prompts directory."""
    prompt_path = PROMPTS_DIR / filename
    return prompt_path.read_text(encoding="utf-8")


def render_prompt_template(template: str, values: dict[str, Any]) -> str:
    """Render {placeholder} values while leaving unknown tokens untouched."""

    def replacer(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            return match.group(0)
        value = values[key]
        return "" if value is None else str(value)

    return PLACEHOLDER_PATTERN.sub(replacer, template)
