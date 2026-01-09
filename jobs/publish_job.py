"""Publish job implementation."""
import logging
from typing import Dict, Any, Optional
import db
import wp_client
from generator.image_gemini import generate_featured_image

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
        # Multi-language drafts
        translations_map = {}
        for lang, draft in payload["drafts"].items():
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
        if "_image" in draft:
            try:
                db.add_job_step(job_id, f"generate_image_{lang}", "running")
                image_data = draft["_image"]

                # Decode base64 back to bytes if needed
                if "bytes_base64" in image_data:
                    import base64
                    image_bytes = base64.b64decode(image_data["bytes_base64"])
                else:
                    # Legacy support for old format
                    image_bytes = image_data["bytes"]

                mime_type = image_data.get("mime", "image/jpeg")
                filename = image_data.get("filename", "featured.jpg")

                media = wp_client.upload_media(
                    site, filename, image_bytes, mime_type)
                image_media_id = media.get("id")
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
