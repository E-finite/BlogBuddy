"""Blog post translation via OpenAI."""
import json
import logging
from typing import Dict, Any
from openai import OpenAI
from src import config
from src.prompt_templates import load_prompt_template, render_prompt_template

logger = logging.getLogger(__name__)
client = OpenAI(api_key=config.OPENAI_API_KEY)

LANGUAGE_NAMES = {
    "en": "English",
    "nl": "Dutch",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
}


def translate_blog(draft_data: Dict[str, Any], target_language: str) -> Dict[str, Any]:
    """
    Translate a blog post draft to the target language using OpenAI.

    Args:
        draft_data: Dict with keys: title, slug, excerpt, contentHtml, yoast, tags, categories
        target_language: ISO language code (e.g. "en")

    Returns:
        Translated draft dict with the same structure.
    """
    target_lang_name = LANGUAGE_NAMES.get(target_language, target_language)

    # Build the subset of draft fields to translate
    translatable = {
        "title": draft_data.get("title", ""),
        "slug": draft_data.get("slug", ""),
        "excerpt": draft_data.get("excerpt", ""),
        "contentHtml": draft_data.get("contentHtml", ""),
        "yoast": draft_data.get("yoast", {}),
        "tags": draft_data.get("tags", []),
        "categories": draft_data.get("categories", []),
    }

    system_prompt = render_prompt_template(
        load_prompt_template("translate_blog_system_prompt.txt"),
        {"target_language": target_lang_name},
    )

    user_prompt = render_prompt_template(
        load_prompt_template("translate_blog_user_prompt.txt"),
        {
            "target_language": target_lang_name,
            "blog_json": json.dumps(translatable, ensure_ascii=False, indent=2),
        },
    )

    response = client.chat.completions.create(
        model=config.OPENAI_TRANSLATION_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = response.choices[0].message.content
    translated = json.loads(raw)

    # Ensure all expected keys are present, fall back to original if missing
    for key in translatable:
        if key not in translated:
            translated[key] = translatable[key]

    # Preserve language metadata
    translated["language"] = target_language

    logger.info(
        "Translated blog '%s' to %s (tokens: %s)",
        draft_data.get("title", "")[:60],
        target_language,
        response.usage.total_tokens if response.usage else "?",
    )

    return translated
