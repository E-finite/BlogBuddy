"""Image generation using DALL-E 3 (OpenAI)."""
import json
import logging
from typing import Tuple, Optional, Dict, Any
import requests
from src import config
from src.prompt_templates import load_prompt_template, render_prompt_template

logger = logging.getLogger(__name__)


def generate_featured_image(
    topic: str,
    brand: Dict[str, Any] = None,
    language: str = "nl",
    image_settings: Dict[str, Any] = None,
    variation_index: int = 0,
    feedback_chain: list[str] = None,
    reference_image_bytes: Optional[bytes] = None,
    reference_image_mime_type: Optional[str] = None,
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """
    Generate a featured image using DALL-E 3 (OpenAI).

    Args:
        topic: Blog post topic
        brand: Brand info (name, colors, etc.)
        language: Language code
        image_settings: Image generation settings (preset, aspectRatio, etc.)
        variation_index: Which variation number (for seed variation)
        feedback_chain: List of cumulative user feedback for regeneration
        reference_image_bytes: Existing image bytes used as edit context
        reference_image_mime_type: MIME type of reference image

    Returns:
        Tuple of (image_bytes, mime_type, filename, error_message)
        On success: (bytes, mime_type, filename, None)
        On failure: (None, "", "", error_message)
    """
    if brand is None:
        brand = {}
    if image_settings is None:
        image_settings = {}
    if feedback_chain is None:
        feedback_chain = []

    return _generate_image_with_optional_reference(
        topic=topic,
        brand=brand,
        image_settings=image_settings,
        variation_index=variation_index,
        feedback_chain=feedback_chain,
        reference_image_bytes=reference_image_bytes,
        reference_image_mime_type=reference_image_mime_type,
    )


def _generate_image_with_optional_reference(
    topic: str,
    brand: Dict[str, Any],
    image_settings: Dict[str, Any],
    variation_index: int,
    feedback_chain: list[str],
    reference_image_bytes: Optional[bytes],
    reference_image_mime_type: Optional[str],
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """Use edit flow when a reference image is available, with safe fallback."""
    prompt, size, brand_colors, use_brand_colors, preset = _build_prompt_and_settings(
        topic=topic,
        brand=brand,
        image_settings=image_settings,
        feedback_chain=feedback_chain,
    )

    logger.info(
        f"Generating image variation {variation_index} for: {topic}"
    )
    logger.info(
        f"Settings: preset={preset}, aspect_ratio={image_settings.get('aspectRatio', '16:9')}, colors={brand_colors if use_brand_colors else 'default'}"
    )
    if feedback_chain:
        logger.info(f"Feedback chain: {feedback_chain}")

    if reference_image_bytes:
        logger.info(
            "Reference image detected for regeneration; trying OpenAI image edit first"
        )
        edit_result = _try_openai_image_edit(
            topic=topic,
            prompt=prompt,
            size=size,
            variation_index=variation_index,
            reference_image_bytes=reference_image_bytes,
            reference_image_mime_type=reference_image_mime_type,
        )
        if edit_result[0]:
            return edit_result

        logger.warning(
            f"Image edit failed, falling back to prompt-only generation: {edit_result[3]}"
        )

    return _try_dalle3_image(topic, prompt, size, variation_index)


def _build_prompt_and_settings(
    topic: str,
    brand: Dict[str, Any],
    image_settings: Dict[str, Any],
    feedback_chain: list[str],
) -> Tuple[str, str, list[str], bool, str]:
    """Build prompt and resolved image settings shared by generation/edit paths."""
    preset = image_settings.get("preset", "minimal-tech")
    aspect_ratio = image_settings.get("aspectRatio", "16:9")
    style_strength = image_settings.get("styleStrength", "medium")
    use_brand_colors = image_settings.get("useBrandColors", False)
    brand_colors = brand.get("colors", [])
    composition = image_settings.get("composition", "auto")
    lighting = image_settings.get("lighting", "soft-studio")

    style_presets = {
        "minimal-tech": "Clean, minimalist, modern tech aesthetic with geometric shapes",
        "bold-creative": "Bold, creative, vibrant with strong visual elements",
        "professional": "Professional, corporate, clean business aesthetic",
        "modern-gradient": "Modern gradient design with smooth color transitions",
        "flat-illustration": "Flat illustration style with simple shapes and colors"
    }
    style_desc = style_presets.get(preset, style_presets["minimal-tech"])

    lighting_desc = {
        "soft-studio": "soft studio lighting, even illumination",
        "natural": "natural daylight, soft shadows",
        "dramatic": "dramatic lighting with strong contrast",
        "backlit": "backlit subject with rim lighting"
    }.get(lighting, "soft studio lighting")

    composition_desc = {
        "auto": "",
        "centered": "centered hero composition",
        "left-whitespace": "subject on left with generous whitespace on right",
        "flat-lay": "flat lay top-down perspective",
        "isometric": "isometric 3D perspective"
    }.get(composition, "")

    color_instruction = ""
    if use_brand_colors and brand_colors:
        color_hex_list = ", ".join(brand_colors)
        color_instruction = f"\nColor palette: {color_hex_list}"

    strength_modifier = {
        "low": "subtle",
        "medium": "",
        "high": "bold and striking"
    }.get(style_strength, "")

    prompt_template = load_prompt_template("image_gemini_base_prompt.txt")
    prompt = render_prompt_template(
        prompt_template,
        {
            "topic": topic,
            "style_desc": style_desc,
            "strength_modifier": strength_modifier,
            "composition_desc": composition_desc,
            "lighting_desc": lighting_desc,
            "color_instruction": color_instruction,
        },
    )

    if feedback_chain:
        feedback_template = load_prompt_template(
            "image_gemini_feedback_appendix.txt"
        )
        numbered_feedback = "\n".join(
            f"{i}. {feedback}" for i, feedback in enumerate(feedback_chain, 1)
        )
        prompt += "\n\n" + render_prompt_template(
            feedback_template,
            {"numbered_feedback_list": numbered_feedback},
        )

    size_map = {
        "1:1": "1024x1024",
        "16:9": "1792x1024",
        "9:16": "1024x1792"
    }
    size = size_map.get(aspect_ratio, "1792x1024")

    return prompt, size, brand_colors, use_brand_colors, preset


def _try_dalle3_image(
    topic: str,
    prompt: str,
    size: str,
    variation_index: int,
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """Try DALL-E 3 API with customizable settings.

    Returns:
        Tuple of (image_bytes, mime_type, filename, error_message)
        If successful, error_message is None
        If failed, image_bytes is None and error_message contains the error
    """
    try:
        # DALL-E 3 API request
        url = "https://api.openai.com/v1/images/generations"

        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": "standard",
            "response_format": "b64_json"
        }

        logger.info(f"Sending request to DALL-E 3 API...")
        logger.info(f"Size: {size}, Prompt length: {len(prompt)} characters")

        response = requests.post(
            url, json=payload, headers=headers, timeout=120)

        logger.info(f"DALL-E 3 API response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            if "data" in result and len(result["data"]) > 0:
                image_data = result["data"][0]

                # Extract base64 image
                import base64
                if "b64_json" in image_data:
                    image_bytes = base64.b64decode(image_data["b64_json"])
                    filename = f"featured-{topic[:30].replace(' ', '-').lower()}-var{variation_index}.png"
                    logger.info(
                        f"DALL-E 3 image generated successfully ({len(image_bytes)} bytes)")
                    return image_bytes, "image/png", filename, None
                else:
                    error_msg = f"No b64_json in response data: {list(image_data.keys())}"
                    logger.warning(error_msg)
                    return None, "", "", error_msg
            else:
                error_msg = f"No data in API response. Response keys: {list(result.keys())}"
                logger.warning(error_msg)
                return None, "", "", error_msg
        else:
            error_detail = response.text[:1000] if response.text else "No error details"
            error_msg = f"DALL-E 3 API error {response.status_code}"

            logger.error(f"{error_msg}: {error_detail}")

            # Parse OpenAI error message
            try:
                error_json = response.json()
                if "error" in error_json:
                    if isinstance(error_json['error'], dict) and 'message' in error_json['error']:
                        error_msg = f"OpenAI: {error_json['error']['message']}"
                    else:
                        error_msg = f"OpenAI: {str(error_json['error'])[:200]}"
                    logger.error(f"Structured error: {error_msg}")
            except:
                pass

            return None, "", "", error_msg

    except Exception as e:
        error_msg = f"Exception during image generation: {str(e)}"
        logger.warning(error_msg, exc_info=True)
        return None, "", "", error_msg


def _try_openai_image_edit(
    topic: str,
    prompt: str,
    size: str,
    variation_index: int,
    reference_image_bytes: bytes,
    reference_image_mime_type: Optional[str],
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """Try OpenAI image edits with the previous image as explicit context."""
    try:
        url = "https://api.openai.com/v1/images/edits"
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        }
        edit_size = _edit_compatible_size(size)

        mime_type = reference_image_mime_type or "image/png"
        extension = _extension_for_mime_type(mime_type)
        files = {
            "image": (f"reference.{extension}", reference_image_bytes, mime_type)
        }

        # `gpt-image-1` supports image edits and lets us reuse the previous image as context.
        data = {
            "model": "gpt-image-1",
            "prompt": prompt,
            "size": edit_size,
            "quality": "medium",
            "response_format": "b64_json",
        }

        logger.info(
            f"Sending request to OpenAI image edits API with reference image ({len(reference_image_bytes)} bytes, size={edit_size})..."
        )
        response = requests.post(url, headers=headers, data=data, files=files, timeout=180)

        logger.info(f"Image edits API response status: {response.status_code}")
        if response.status_code != 200:
            error_detail = response.text[:1000] if response.text else "No error details"
            error_msg = f"OpenAI image edit error {response.status_code}"
            logger.error(f"{error_msg}: {error_detail}")

            try:
                error_json = response.json()
                if "error" in error_json:
                    if isinstance(error_json["error"], dict) and "message" in error_json["error"]:
                        error_msg = f"OpenAI: {error_json['error']['message']}"
                    else:
                        error_msg = f"OpenAI: {str(error_json['error'])[:200]}"
            except Exception:
                pass

            return None, "", "", error_msg

        result = response.json()
        image_bytes, output_mime_type, output_extension = _extract_openai_image_bytes(result)
        if not image_bytes:
            error_msg = "No image data in OpenAI image edit response"
            logger.warning(f"{error_msg}. Response keys: {list(result.keys())}")
            return None, "", "", error_msg

        filename = f"featured-{topic[:30].replace(' ', '-').lower()}-var{variation_index}.{output_extension}"
        logger.info(
            f"OpenAI image edit generated successfully ({len(image_bytes)} bytes, {output_mime_type})"
        )
        return image_bytes, output_mime_type, filename, None

    except Exception as e:
        error_msg = f"Exception during image edit generation: {str(e)}"
        logger.warning(error_msg, exc_info=True)
        return None, "", "", error_msg


def _extract_openai_image_bytes(result: Dict[str, Any]) -> Tuple[Optional[bytes], str, str]:
    """Decode image bytes from OpenAI Images API response."""
    data_items = result.get("data") or []
    if not data_items:
        return None, "", ""

    first_item = data_items[0]
    if "b64_json" in first_item:
        import base64

        image_bytes = base64.b64decode(first_item["b64_json"])
        return image_bytes, "image/png", "png"

    image_url = first_item.get("url")
    if image_url:
        download = requests.get(image_url, timeout=60)
        if download.status_code == 200 and download.content:
            response_mime_type = download.headers.get("Content-Type", "image/png").split(";")[0]
            extension = _extension_for_mime_type(response_mime_type)
            return download.content, response_mime_type, extension

    return None, "", ""


def _extension_for_mime_type(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return "jpg"
    if mime_type == "image/webp":
        return "webp"
    return "png"


def _edit_compatible_size(size: str) -> str:
    """Map generation sizes to sizes commonly supported by image edit models."""
    size_map = {
        "1792x1024": "1536x1024",
        "1024x1792": "1024x1536",
    }
    return size_map.get(size, size)
