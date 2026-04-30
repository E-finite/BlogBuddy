"""Draft builder orchestrator."""
import logging
from typing import Dict, Any, List
from src.generator.text_openai import generate_post_content
from src.generator.image_gemini import generate_featured_image
from src import db

logger = logging.getLogger(__name__)


def build_draft(
    topic: str,
    audience: Dict[str, Any],
    tone_of_voice: Dict[str, Any],
    seo: Dict[str, Any],
    brand: Dict[str, Any],
    language: str = "nl",
    generate_image: bool = True,
    site_id: str = None,
    image_settings: Dict[str, Any] = None,
    user_id: int = None,
    job_id: str = None
) -> Dict[str, Any]:
    """
    Build a complete draft with content and optional image.

    Args:
        generate_image: Whether to generate a featured image with DALL-E
        site_id: Optional site ID for website context retrieval
        image_settings: Optional image generation settings (preset, colors, etc.)
        user_id: User ID for saving images to database
        job_id: Job ID for linking images to publish job

    Returns:
        Dict with draft content (title, slug, excerpt, contentHtml, yoast, tags, categories)
        and optional image data
    """
    # Prepare internal link targets
    internal_link_targets = []
    for target in seo.get("internalLinkTargets", []):
        internal_link_targets.append({
            "title": target.get("title", ""),
            "url": target.get("url", ""),
            "description": target.get("description", ""),
        })

    # Build website context bundle if site_id provided
    website_context_bundle = None
    if site_id:
        try:
            from context.context_retrieval import build_context_bundle
            website_context_bundle = build_context_bundle(
                site_id=site_id,
                topic=topic,
                seo=seo,
                audience=audience,
                max_snippets=6
            )
            logger.info(
                f"Built website context bundle with {len(website_context_bundle.get('relevant_snippets', []))} snippets")
        except Exception as e:
            logger.warning(f"Could not build website context bundle: {e}")
            website_context_bundle = None

    # Generate text content
    content = generate_post_content(
        topic=topic,
        audience=audience,
        tone_of_voice=tone_of_voice,
        seo=seo,
        brand=brand,
        language=language,
        internal_link_targets=internal_link_targets,
        website_context_bundle=website_context_bundle
    )

    # Ensure excerpt is 1-2 sentences
    excerpt = content.get("excerpt", "")
    sentences = excerpt.split(". ")
    if len(sentences) > 2:
        excerpt = ". ".join(sentences[:2])
        if not excerpt.endswith("."):
            excerpt += "."
        content["excerpt"] = excerpt

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

    # Generate featured image(s) - supports multiple variations
    images = []
    image_ids = []
    if generate_image and user_id:
        if image_settings is None:
            image_settings = {}

        variations_count = image_settings.get("variations", 1)

        # Generate multiple variations
        for i in range(variations_count):
            image_bytes, mime_type, filename, error_msg = generate_featured_image(
                topic=topic,
                brand=brand,
                language=language,
                image_settings=image_settings,
                variation_index=i
            )

            if image_bytes:
                # Build prompt for storage (for debugging/audit)
                import json
                prompt = f"Topic: {topic}, Settings: {json.dumps(image_settings)}"

                # Save to database
                image_id = db.save_image_generation(
                    user_id=user_id,
                    topic=topic,
                    image_settings=image_settings,
                    prompt_used=prompt,
                    image_data=image_bytes,
                    mime_type=mime_type,
                    filename=filename,
                    brand=brand,
                    job_id=job_id
                )

                image_ids.append(image_id)

                # Also keep base64 for backward compatibility with existing frontend
                import base64
                images.append({
                    "imageId": image_id,
                    "bytes_base64": base64.b64encode(image_bytes).decode('utf-8'),
                    "mime_type": mime_type,
                    "filename": filename or f"featured-{content.get('slug', 'featured')}-{i}.jpg"
                })

    draft = {
        **content,
        "language": language
    }

    # Store images - single or multiple variations
    if images:
        if len(images) == 1:
            # Single image - use old format for compatibility
            draft["image"] = images[0]
            draft["imageId"] = image_ids[0] if image_ids else None
        else:
            # Multiple variations - store all
            draft["images"] = images
            draft["image"] = images[0]  # Default to first one
            draft["imageIds"] = image_ids

    return draft


def build_multilang_drafts(
    topic: str,
    audience: Dict[str, Any],
    tone_of_voice: Dict[str, Any],
    seo: Dict[str, Any],
    brand: Dict[str, Any],
    languages: List[str],
    strategy: str = "translate",
    generate_image: bool = True,
    site_id: str = None
) -> Dict[str, Dict[str, Any]]:
    """
    Build drafts for multiple languages.

    Args:
        strategy: "translate" (direct translation) or "localize" (adapt for local market)
        generate_image: Whether to generate a featured image with DALL-E
        site_id: Optional site ID for website context retrieval
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
            generate_image=generate_image and lang == languages[0],
            site_id=site_id
        )

        # If not the first language, instruct to translate/localize
        if lang != languages[0] and strategy == "translate":
            # Re-generate with translation instruction
            # For MVP, we'll use the same generation but with language parameter
            # In production, you might want to pass the original draft for context
            pass

        drafts[lang] = draft

    return drafts
