"""OpenAI text generation using Responses API."""
import json
import logging
import re
from typing import Dict, Any
from openai import OpenAI
from src import config
from src.prompt_templates import load_prompt_template, render_prompt_template

logger = logging.getLogger(__name__)
client = OpenAI(api_key=config.OPENAI_API_KEY)

_HTML_TAG = re.compile(r'<[a-zA-Z][^>]*>')


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


# Sections that can be individually regenerated
REGENERATABLE_SECTIONS = {
    "title":       "Genereer een nieuwe pakkende blogtitel",
    "excerpt":     "Genereer een nieuwe inleidende alinea / samenvatting (1-2 zinnen)",
    "contentHtml": "Genereer de volledige blogtekst als HTML",
    "yoast":       "Genereer de SEO-metadata (seo_title, meta_desc, focuskw)",
    "tags":        "Genereer de tags en categorieën",
    "full":        "Hergenereer het volledige blogartikel",
}

_SECTION_JSON_SCHEMAS = {
    "title":       '{"title": "...", "slug": "..."}',
    "excerpt":     '{"excerpt": "..."}',
    "contentHtml": '{"contentHtml": "..."}',
    "yoast":       '{"yoast": {"focuskw": "...", "seo_title": "...", "meta_desc": "..."}}',
    "tags":        '{"tags": ["..."], "categories": ["..."]}',
    "full": (
        '{"title": "...", "slug": "...", "excerpt": "...", "contentHtml": "...",'
        ' "yoast": {"focuskw": "...", "seo_title": "...", "meta_desc": "..."},'
        ' "tags": ["..."], "categories": ["..."]}'
    ),
}


def regenerate_section(
    section: str,
    instruction: str,
    current_draft: Dict[str, Any],
    language: str = "nl",
) -> Dict[str, Any]:
    """
    Regenerate one or all sections of an existing draft using the same model
    as the full generation pipeline.

    Args:
        section:       One of the REGENERATABLE_SECTIONS keys.
        instruction:   Free-form adjustment instruction from the user.
        current_draft: The current draft dict (title, slug, excerpt, contentHtml, yoast, tags, categories).
        language:      Language code (default 'nl').

    Returns:
        Dict containing only the regenerated key(s).
    """
    if section not in REGENERATABLE_SECTIONS:
        raise ValueError(
            f"Onbekend onderdeel '{section}'. Kies uit: {', '.join(REGENERATABLE_SECTIONS)}"
        )

    json_schema = _SECTION_JSON_SCHEMAS[section]
    section_label = REGENERATABLE_SECTIONS[section]

    title = current_draft.get("title", "")
    excerpt = current_draft.get("excerpt", "")
    content_html = current_draft.get("contentHtml", "")
    yoast = current_draft.get("yoast", {})
    tags = current_draft.get("tags", [])
    categories = current_draft.get("categories", [])

    system_prompt = (
        f"Je bent een professionele content-editor die werkt in de taal: {language}.\n"
        "Je ontvangt het huidige blogconcept en een aanpasinstructie van de gebruiker.\n"
        f"Taak: {section_label}.\n"
        "Geef ALLEEN het gevraagde onderdeel terug als geldig JSON-object "
        f"met exact dit schema:\n{json_schema}\n"
        "Gebruik de taal die opgegeven is. Geef geen uitleg, alleen JSON."
    )

    current_draft_summary = (
        f"Huidige titel: {title}\n"
        f"Huidige excerpt: {excerpt}\n"
        f"Huidige SEO (yoast): {json.dumps(yoast, ensure_ascii=False)}\n"
        f"Huidige tags: {json.dumps(tags, ensure_ascii=False)}\n"
        f"Huidige categorieën: {json.dumps(categories, ensure_ascii=False)}\n"
    )

    if section in ("contentHtml", "full"):
        current_draft_summary += f"\nHuidige content (HTML, ingekort):\n{content_html[:2000]}"

    user_prompt = (
        f"Aanpasinstructie van de gebruiker: {instruction}\n\n"
        f"Huidig concept:\n{current_draft_summary}\n\n"
        f"Geef nu de hergegenereerde versie van '{section}' terug als JSON."
    )

    response = client.chat.completions.create(
        model=config.OPENAI_TEXT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
        max_completion_tokens=3000,
    )

    result = json.loads(response.choices[0].message.content)

    # Normalise slug if title was regenerated
    if "slug" in result and result.get("slug"):
        result["slug"] = result["slug"].lower().replace(
            " ", "-").replace("_", "-")

    return result


def regenerate_inline_selection(
    selected_text: str,
    instruction: str,
    context_before: str = "",
    context_after: str = "",
    language: str = "nl",
) -> str:
    """
    Rewrite a specific selected fragment from the draft based on a user instruction.
    Automatically detects whether the content is HTML or plain text.

    Returns:
        The replacement text (HTML or plain, matching the input format).
    """
    is_html = bool(
        _HTML_TAG.search(selected_text)
        or _HTML_TAG.search(context_before)
        or _HTML_TAG.search(context_after)
    )
    format_hint = "HTML (behoud vergelijkbare HTML-tags, gebruik geen markdown)" if is_html else "plain tekst"

    system_prompt = (
        f"Je bent een professionele content-editor die werkt in de taal: {language}.\n"
        f"Je ontvangt een fragment uit een blogartikel en een aanpasinstructie.\n"
        f"Geef ALLEEN het herschreven fragment terug als {format_hint}, "
        f"zonder uitleg, zonder code blocks.\n"
        f"Het herschreven fragment moet naadloos passen in de omringende context."
    )

    context_section = ""
    if context_before or context_after:
        context_section = (
            f"\n\nContext vóór de selectie:\n{context_before}\n\n"
            f"Context ná de selectie:\n{context_after}"
        )

    user_prompt = (
        f"Geselecteerd fragment:\n{selected_text}\n\n"
        f"Aanpasinstructie: {instruction}"
        f"{context_section}\n\n"
        f"Geef nu het herschreven fragment terug."
    )

    response = client.chat.completions.create(
        model=config.OPENAI_TEXT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_completion_tokens=2000,
    )

    return response.choices[0].message.content.strip()
