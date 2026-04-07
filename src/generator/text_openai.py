"""OpenAI text generation using Responses API."""
import json
import logging
from typing import Dict, Any
from openai import OpenAI
from src import config
from src.prompt_templates import load_prompt_template, render_prompt_template

logger = logging.getLogger(__name__)
client = OpenAI(api_key=config.OPENAI_API_KEY)


def generate_post_content(
    topic: str,
    audience: Dict[str, Any],
    tone_of_voice: Dict[str, Any],
    seo: Dict[str, Any],
    brand: Dict[str, Any],
    language: str = "nl",
    internal_link_targets: list = None,
    website_context_bundle: Dict[str, Any] = None,
    form_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Generate blog post content using OpenAI Responses API.

    Returns:
        Dict with keys: title, slug, excerpt, contentHtml, yoast (focuskw, seo_title, meta_desc), tags, categories
    """
    if internal_link_targets is None:
        internal_link_targets = []
    if website_context_bundle is None:
        website_context_bundle = {}
    if form_data is None:
        form_data = {}

    # Optional invalshoek vanuit formulier data
    current_angle = form_data.get('angle', 'Uitgebreide gids met tips')

    # Build website context section from template
    website_context_section = ""
    if website_context_bundle:
        website_context_template = load_prompt_template(
            "text_openai_website_context_section.txt"
        )
        website_context_section = render_prompt_template(
            website_context_template,
            {
                "website_context_bundle_json": json.dumps(
                    website_context_bundle, ensure_ascii=False, indent=2
                )
            },
        )

    # Build system prompt from template
    system_prompt_template = load_prompt_template(
        "text_openai_system_prompt.txt")
    system_prompt = render_prompt_template(
        system_prompt_template,
        {
            "brand_name": brand.get("name", "het merk"),
            "language": language,
            "website_context_section": website_context_section,
            "current_angle": current_angle,
            "focus_keyword": seo.get("focusKeyword", ""),
            "secondary_keywords": ", ".join(seo.get("secondaryKeywords", [])),
            "tone_style": ", ".join(tone_of_voice.get("style", [])),
            "audience_level": audience.get("level", "intermediate"),
        },
    )

    user_prompt_template = load_prompt_template("text_openai_user_prompt.txt")
    user_prompt = render_prompt_template(
        user_prompt_template,
        {
            "topic": topic,
            "current_angle": current_angle,
            "pain_points": ", ".join(audience.get("painPoints", [])),
        },
    )

    try:
        response = client.chat.completions.create(
            model=config.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_completion_tokens=3000
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        # Validate required fields
        required_fields = ["title", "slug", "excerpt", "contentHtml", "yoast"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")

        if "focuskw" not in result["yoast"] or "seo_title" not in result["yoast"] or "meta_desc" not in result["yoast"]:
            raise ValueError("Missing required yoast fields")

        # Ensure meta_desc length
        if len(result["yoast"]["meta_desc"]) > seo.get("metaDescMaxLen", 155):
            result["yoast"]["meta_desc"] = result["yoast"]["meta_desc"][:seo.get(
                "metaDescMaxLen", 155)].rstrip()

        # Ensure slug is kebab-case
        result["slug"] = result["slug"].lower().replace(
            " ", "-").replace("_", "-")

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from OpenAI: {e}")
        # Retry once with the same prompt and a lower temperature.
        logger.info("Retrying generation with lower temperature...")
        response = client.chat.completions.create(
            model=config.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_completion_tokens=3000
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        return result
