"""Draft builder orchestrator."""
import logging
from typing import Dict, Any, List
from generator.text_openai import generate_post_content
from generator.image_gemini import generate_featured_image

logger = logging.getLogger(__name__)


def build_draft(
    topic: str,
    audience: Dict[str, Any],
    tone_of_voice: Dict[str, Any],
    seo: Dict[str, Any],
    brand: Dict[str, Any],
    language: str = "nl",
    generate_image: bool = True
) -> Dict[str, Any]:
    """
    Build a complete draft with content and optional image.

    Args:
        generate_image: Whether to generate a featured image with DALL-E

    Returns:
        Dict with draft content (title, slug, excerpt, contentHtml, yoast, tags, categories)
        and optional image data
    """
    # Prepare internal link targets
    internal_link_targets = []
    for target in seo.get("internalLinkTargets", []):
        internal_link_targets.append({
            "title": target.get("title", ""),
            "url": target.get("url", "")
        })

    # Generate text content
    content = generate_post_content(
        topic=topic,
        audience=audience,
        tone_of_voice=tone_of_voice,
        seo=seo,
        brand=brand,
        language=language,
        internal_link_targets=internal_link_targets
    )

    # Ensure excerpt is 1-2 sentences
    excerpt = content.get("excerpt", "")
    sentences = excerpt.split(". ")
    if len(sentences) > 2:
        excerpt = ". ".join(sentences[:2])
        if not excerpt.endswith("."):
            excerpt += "."
        content["excerpt"] = excerpt

    # Ensure meta desc is hard capped
    meta_desc = content.get("yoast", {}).get("meta_desc", "")
    max_len = seo.get("metaDescMaxLen", 155)
    if len(meta_desc) > max_len:
        content["yoast"]["meta_desc"] = meta_desc[:max_len].rstrip()

    # Ensure slug is kebab-case and includes focus keyword if possible
    slug = content.get("slug", "")
    focus_keyword = seo.get("focusKeyword", "").lower().replace(" ", "-")
    if focus_keyword and focus_keyword not in slug:
        # Try to incorporate focus keyword
        slug_parts = slug.split("-")
        if len(slug_parts) > 3:
            slug = "-".join([focus_keyword] + slug_parts[:2])
        else:
            slug = f"{focus_keyword}-{slug}"
    content["slug"] = slug

    # Generate featured image (optional, won't fail if it doesn't work)
    image_bytes, mime_type, filename = None, "", ""
    if generate_image:
        image_bytes, mime_type, filename = generate_featured_image(
            topic=topic,
            brand_name=brand.get("name", ""),
            language=language
        )

    draft = {
        **content,
        "language": language
    }

    if image_bytes:
        # Convert bytes to base64 for JSON serialization
        import base64
        draft["_image"] = {
            "bytes_base64": base64.b64encode(image_bytes).decode('utf-8'),
            "mime": mime_type,
            "filename": filename or f"featured-{slug}.jpg"
        }

    return draft


def build_multilang_drafts(
    topic: str,
    audience: Dict[str, Any],
    tone_of_voice: Dict[str, Any],
    seo: Dict[str, Any],
    brand: Dict[str, Any],
    languages: List[str],
    strategy: str = "translate",
    generate_image: bool = True
) -> Dict[str, Dict[str, Any]]:
    """
    Build drafts for multiple languages.

    Args:
        strategy: "translate" (direct translation) or "localize" (adapt for local market)
        generate_image: Whether to generate a featured image with DALL-E
    """
    drafts = {}

    for lang in languages:
        # For localization, we might adjust topic/audience per language
        # For MVP, we'll use the same inputs but instruct OpenAI to translate/localize
        lang_topic = topic
        if strategy == "localize" and lang != "nl":
            # Could add localization logic here
            pass

        draft = build_draft(
            topic=lang_topic,
            audience=audience,
            tone_of_voice=tone_of_voice,
            seo=seo,
            brand=brand,
            language=lang,
            # Only generate image for first language
            generate_image=generate_image and lang == languages[0]
        )

        # If not the first language, instruct to translate/localize
        if lang != languages[0] and strategy == "translate":
            # Re-generate with translation instruction
            # For MVP, we'll use the same generation but with language parameter
            # In production, you might want to pass the original draft for context
            pass

        drafts[lang] = draft

    return drafts
