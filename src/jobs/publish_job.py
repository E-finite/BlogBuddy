"""Publish job implementation."""
import logging
from typing import Dict, Any, Optional
from src import db
from src import wp_client
from src.generator.image_gemini import generate_featured_image

logger = logging.getLogger(__name__)


def execute_publish_job(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a publish job.

    Payload structure:
    {
        "siteId": "...",
        "draft": {...} OR
        "drafts": {"nl": {...}, "en": {...}}
    }
    """
    site_id = payload["siteId"]
    site = db.get_site(site_id)
    if not site:
        raise ValueError(f"Site {site_id} not found")

    result = {
        "wpPostIds": {},
        "errors": []
    }

    # Check if single draft or multi-language drafts
    if "draft" in payload:
        # Single draft
        post_id = _publish_single_draft(site, payload["draft"], job_id)
        if post_id:
            result["wpPostIds"]["default"] = post_id
        else:
            result["errors"].append("Failed to publish single draft")
    elif "drafts" in payload:
        drafts = payload["drafts"]
        original_lang = next(iter(drafts))  # First language is the original

        # If there are translations, check if the translation plugin is active
        if len(drafts) > 1:
            db.add_job_step(job_id, "check_translation_plugin", "running")
            plugin_check = wp_client.check_translation_plugin(site)

            if not plugin_check.get("available"):
                # No translation plugin — only publish the original
                logger.warning(
                    "No translation plugin detected on WordPress. "
                    "Publishing only the original language.")
                db.add_job_step(
                    job_id, "check_translation_plugin", "skipped",
                    {"reason": "no_translation_plugin"})

                skipped_langs = [l for l in drafts if l != original_lang]
                result["warnings"] = result.get("warnings", [])
                result["warnings"].append(
                    f"Er is geen vertaal-plugin (Polylang, WPML of TranslatePress) "
                    f"gedetecteerd op je WordPress site. "
                    f"Alleen de originele versie ({original_lang}) is gepubliceerd. "
                    f"De vertalingen ({', '.join(skipped_langs)}) zijn overgeslagen. "
                    f"Installeer en activeer een vertaal-plugin om vertalingen te publiceren."
                )

                # Publish only original
                drafts = {original_lang: drafts[original_lang]}
            else:
                db.add_job_step(
                    job_id, "check_translation_plugin", "success")

        # Publish each language draft
        translations_map = {}
        for lang, draft in drafts.items():
            try:
                post_id = _publish_single_draft(site, draft, job_id, lang)
                if post_id:
                    result["wpPostIds"][lang] = post_id
                    translations_map[lang] = post_id
                else:
                    result["errors"].append(
                        f"Failed to publish draft for {lang}")
            except Exception as e:
                logger.error(f"Error publishing draft for {lang}: {e}")
                result["errors"].append(f"Error publishing {lang}: {str(e)}")

        # Link translations via Polylang
        if len(translations_map) > 1:
            try:
                db.add_job_step(job_id, "link_translations", "running", {
                                "translations": translations_map})
                polylang_result = wp_client.link_polylang_translations(
                    site, translations_map)
                if polylang_result.get("status") == "skipped":
                    db.add_job_step(job_id, "link_translations", "skipped", {
                                    "reason": "endpoint_not_found"})
                    logger.warning(
                        "Polylang linking skipped - endpoint not found")
                else:
                    db.add_job_step(job_id, "link_translations",
                                    "success", polylang_result)
            except Exception as e:
                logger.error(f"Error linking Polylang translations: {e}")
                db.add_job_step(job_id, "link_translations",
                                "failed", {"error": str(e)})
                # Don't fail the whole job if Polylang fails
                result["errors"].append(f"Polylang linking failed: {str(e)}")

    return result


def _publish_single_draft(
    site: Dict[str, Any],
    draft: Dict[str, Any],
    job_id: str,
    lang: str = "default"
) -> Optional[int]:
    """
    Publish a single draft to WordPress.

    Returns:
        WordPress post ID or None on failure
    """
    db.add_job_step(job_id, f"publish_draft_{lang}", "running")

    try:
        # Step A: Generate featured image (optional)
        image_media_id = None
        image_id = None
        # Support both "image" and "_image" field names
        image_data = draft.get("image") or draft.get("_image")

        if image_data:
            try:
                db.add_job_step(job_id, f"generate_image_{lang}", "running")

                # Check if image is stored in database (new format)
                if "imageId" in image_data:
                    image_id = image_data["imageId"]
                    # Load from database
                    import src.db as db_module
                    # Get without user check (job context - already authorized via site ownership)
                    conn = db_module.get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("""
                        SELECT * FROM image_generations WHERE id = %s
                    """, (image_id,))
                    image_gen = cursor.fetchone()
                    cursor.close()
                    conn.close()

                    if image_gen and image_gen['image_data']:
                        image_bytes = image_gen['image_data']
                        mime_type = image_gen['mime_type']
                        filename = image_gen['filename']
                    else:
                        # Fallback to base64 if DB load fails
                        if "bytes_base64" in image_data:
                            import base64
                            image_bytes = base64.b64decode(
                                image_data["bytes_base64"])
                            mime_type = image_data.get(
                                "mime_type", "image/jpeg")
                            filename = image_data.get(
                                "filename", "featured.jpg")
                        else:
                            raise Exception(
                                "Image data not found in database or draft")
                elif "bytes_base64" in image_data:
                    # Legacy format - base64 in draft
                    import base64
                    image_bytes = base64.b64decode(image_data["bytes_base64"])
                    mime_type = image_data.get("mime_type", "image/jpeg")
                    filename = image_data.get("filename", "featured.jpg")
                else:
                    # Legacy support for old format
                    image_bytes = image_data.get("bytes")
                    mime_type = image_data.get(
                        "mime_type") or image_data.get("mime", "image/jpeg")
                    filename = image_data.get("filename", "featured.jpg")

                media = wp_client.upload_media(
                    site, filename, image_bytes, mime_type)
                image_media_id = media.get("id")

                # Update database with WordPress media ID if image was stored in DB
                if image_id and image_media_id:
                    import src.db as db_module
                    db_module.update_image_uploaded(image_id, image_media_id)

                db.add_job_step(job_id, f"generate_image_{lang}", "success", {
                                "mediaId": image_media_id})
            except Exception as e:
                logger.warning(
                    f"Image generation/upload failed: {e}. Continuing without image.")
                db.add_job_step(job_id, f"generate_image_{lang}", "failed", {
                                "error": str(e)})

        # Step B: Create WordPress post
        db.add_job_step(job_id, f"create_post_{lang}", "running")

        # Get status and schedule date from original request (stored in draft or payload)
        status = draft.get("status", "draft")
        schedule_date_gmt = draft.get("scheduleDateGmt")

        post_payload = {
            "title": draft["title"],
            "content": draft["contentHtml"],
            "status": status
        }

        # Add optional fields only if they have valid values
        if draft.get("excerpt"):
            post_payload["excerpt"] = draft["excerpt"]

        if draft.get("slug"):
            post_payload["slug"] = draft["slug"]

        if schedule_date_gmt:
            post_payload["date_gmt"] = schedule_date_gmt

        if image_media_id:
            post_payload["featured_media"] = image_media_id

        # Skip tags and categories for now
        # WordPress API on this site expects tag/category IDs (integers), not names
        # We would need to first query existing tags/categories and map names to IDs
        # or create new ones via the API

        logger.info(
            f"Attempting to create WordPress post with payload keys: {list(post_payload.keys())}")
        try:
            post = wp_client.create_post(site, post_payload)
        except Exception as e:
            logger.error(
                f"Failed to create WordPress post. Draft keys: {list(draft.keys())}")
            logger.error(f"Post payload: {post_payload}")
            raise

        post_id = post.get("id")

        if not post_id:
            raise ValueError("WordPress post creation returned no ID")

        db.add_job_step(job_id, f"create_post_{lang}", "success", {
                        "postId": post_id})

        # Step C: Set Yoast SEO meta
        if "yoast" in draft:
            try:
                db.add_job_step(job_id, f"set_yoast_{lang}", "running")
                yoast = draft["yoast"]
                yoast_result = wp_client.set_yoast_meta(
                    site,
                    post_id,
                    yoast.get("focuskw", ""),
                    yoast.get("seo_title", ""),
                    yoast.get("meta_desc", "")
                )
                if yoast_result.get("status") == "skipped":
                    db.add_job_step(job_id, f"set_yoast_{lang}", "skipped", {
                                    "reason": "endpoint_not_found"})
                else:
                    db.add_job_step(
                        job_id, f"set_yoast_{lang}", "success", yoast_result)
            except Exception as e:
                logger.warning(f"Yoast meta setting failed: {e}")
                db.add_job_step(job_id, f"set_yoast_{lang}", "failed", {
                                "error": str(e)})

        db.add_job_step(job_id, f"publish_draft_{lang}", "success", {
                        "postId": post_id})
        return post_id

    except Exception as e:
        logger.error(f"Error publishing draft: {e}")
        db.add_job_step(job_id, f"publish_draft_{lang}", "failed", {
                        "error": str(e)})
        raise
