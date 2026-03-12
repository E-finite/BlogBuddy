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
    feedback_chain: list[str] = None
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

    return _try_dalle3_image(topic, brand, image_settings, variation_index, feedback_chain)


def _try_dalle3_image(
    topic: str,
    brand: Dict[str, Any],
    image_settings: Dict[str, Any],
    variation_index: int,
    feedback_chain: list[str]
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """Try DALL-E 3 API with customizable settings.

    Returns:
        Tuple of (image_bytes, mime_type, filename, error_message)
        If successful, error_message is None
        If failed, image_bytes is None and error_message contains the error
    """
    try:
        # Extract settings
        preset = image_settings.get("preset", "minimal-tech")
        aspect_ratio = image_settings.get("aspectRatio", "16:9")
        style_strength = image_settings.get("styleStrength", "medium")
        use_brand_colors = image_settings.get("useBrandColors", False)
        brand_colors = brand.get("colors", [])
        composition = image_settings.get("composition", "auto")
        lighting = image_settings.get("lighting", "soft-studio")

        # Build style description from preset
        style_presets = {
            "minimal-tech": "Clean, minimalist, modern tech aesthetic with geometric shapes",
            "bold-creative": "Bold, creative, vibrant with strong visual elements",
            "professional": "Professional, corporate, clean business aesthetic",
            "modern-gradient": "Modern gradient design with smooth color transitions",
            "flat-illustration": "Flat illustration style with simple shapes and colors"
        }
        style_desc = style_presets.get(preset, style_presets["minimal-tech"])

        # Build lighting description
        lighting_desc = {
            "soft-studio": "soft studio lighting, even illumination",
            "natural": "natural daylight, soft shadows",
            "dramatic": "dramatic lighting with strong contrast",
            "backlit": "backlit subject with rim lighting"
        }.get(lighting, "soft studio lighting")

        # Build composition description
        composition_desc = {
            "auto": "",
            "centered": "centered hero composition",
            "left-whitespace": "subject on left with generous whitespace on right",
            "flat-lay": "flat lay top-down perspective",
            "isometric": "isometric 3D perspective"
        }.get(composition, "")

        # Build color palette instruction
        color_instruction = ""
        if use_brand_colors and brand_colors:
            color_hex_list = ", ".join(brand_colors)
            color_instruction = f"\nColor palette: {color_hex_list}"

        # Build style strength modifier
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

        # Add cumulative feedback if regenerating
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

        logger.info(
            f"Generating image variation {variation_index} with DALL-E 3 for: {topic}")
        logger.info(
            f"Settings: preset={preset}, aspect_ratio={aspect_ratio}, colors={brand_colors if use_brand_colors else 'default'}")
        if feedback_chain:
            logger.info(f"Feedback chain: {feedback_chain}")

        # Convert aspect ratio to DALL-E 3 format
        size_map = {
            "1:1": "1024x1024",
            "16:9": "1792x1024",
            "9:16": "1024x1792"
        }
        size = size_map.get(aspect_ratio, "1792x1024")

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
