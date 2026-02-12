"""Image generation using Gemini only."""
import logging
from typing import Tuple, Optional, Dict, Any
import requests
from src import config

logger = logging.getLogger(__name__)


def generate_featured_image(
    topic: str,
    brand: Dict[str, Any] = None,
    language: str = "nl",
    image_settings: Dict[str, Any] = None,
    variation_index: int = 0,
    feedback_chain: list[str] = None
) -> Tuple[Optional[bytes], str, str]:
    """
    Generate a featured image using Gemini Imagen.

    Args:
        topic: Blog post topic
        brand: Brand info (name, colors, etc.)
        language: Language code
        image_settings: Image generation settings (preset, aspectRatio, etc.)
        variation_index: Which variation number (for seed variation)
        feedback_chain: List of cumulative user feedback for regeneration

    Returns:
        Tuple of (image_bytes, mime_type, filename) or (None, "", "") on failure
    """
    if brand is None:
        brand = {}
    if image_settings is None:
        image_settings = {}
    if feedback_chain is None:
        feedback_chain = []

    return _try_gemini_image(topic, brand, image_settings, variation_index, feedback_chain)


def _try_gemini_image(
    topic: str,
    brand: Dict[str, Any],
    image_settings: Dict[str, Any],
    variation_index: int,
    feedback_chain: list[str]
) -> Tuple[Optional[bytes], str, str]:
    """Try Gemini Imagen API with customizable settings."""
    try:
        # Extract settings
        preset = image_settings.get("preset", "minimal-tech")
        aspect_ratio = image_settings.get("aspectRatio", "16:9")
        style_strength = image_settings.get("styleStrength", "medium")
        use_brand_colors = image_settings.get("useBrandColors", False)
        brand_colors = brand.get("colors", [])
        composition = image_settings.get("composition", "auto")
        lighting = image_settings.get("lighting", "soft-studio")
        negative_prompt = image_settings.get(
            "negativePrompt", "blurry, low quality, watermark, text overlay")

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

        prompt = f"""Create a professional blog header image about: {topic}

Style: {style_desc} {strength_modifier}
{composition_desc}
Lighting: {lighting_desc}{color_instruction}

Requirements:
- No text or logos
- Professional and visually appealing
- Suitable for business blog featured image
- High resolution
- Modern aesthetic"""

        # Add cumulative feedback if regenerating
        if feedback_chain:
            prompt += "\n\n### USER REFINEMENTS (REQUIRED):\n"
            prompt += "Apply ALL of the following refinements to the image:\n"
            for i, feedback in enumerate(feedback_chain, 1):
                prompt += f"{i}. {feedback}\n"
            prompt += "\nThese refinements MUST all be visible in the final image."

        logger.info(
            f"Generating image variation {variation_index} with Imagen 4.0 for: {topic}")
        logger.info(
            f"Settings: preset={preset}, aspect_ratio={aspect_ratio}, colors={brand_colors if use_brand_colors else 'default'}")
        if feedback_chain:
            logger.info(f"Feedback chain: {feedback_chain}")
        
        # Log the full prompt for debugging
        logger.debug(f"Full prompt being sent: {prompt[:500]}...")

        # Use correct Imagen API endpoint
        url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"

        headers = {
            "x-goog-api-key": config.GEMINI_API_KEY,
            "Content-Type": "application/json"
        }

        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect_ratio
            }
        }

        # Note: negativePrompt is no longer supported by Imagen API

        # Add seed if locked
        if image_settings.get("lockSeed") and image_settings.get("seedValue"):
            # Vary seed slightly per variation
            payload["parameters"]["seed"] = image_settings["seedValue"] + \
                variation_index

        response = requests.post(
            url, json=payload, headers=headers, timeout=120)

        logger.info(f"Imagen API response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            logger.info(f"Response structure: {result.keys()}")

            # Extract image from predictions
            if "predictions" in result and len(result["predictions"]) > 0:
                prediction = result["predictions"][0]
                logger.info(f"Prediction keys: {prediction.keys()}")

                # Try different possible image data locations
                image_bytes = None

                if "bytesBase64Encoded" in prediction:
                    import base64
                    image_bytes = base64.b64decode(
                        prediction["bytesBase64Encoded"])
                elif "image" in prediction:
                    if isinstance(prediction["image"], str):
                        # Base64 string
                        import base64
                        image_bytes = base64.b64decode(prediction["image"])
                    elif "bytesBase64Encoded" in prediction["image"]:
                        import base64
                        image_bytes = base64.b64decode(
                            prediction["image"]["bytesBase64Encoded"])

                if image_bytes:
                    filename = f"featured-{topic[:30].replace(' ', '-').lower()}-var{variation_index}.png"
                    logger.info(
                        f"Imagen image generated successfully ({len(image_bytes)} bytes)")
                    return image_bytes, "image/png", filename
                else:
                    logger.warning(
                        f"Could not extract image from prediction: {prediction}")
                    return None, "", ""
            else:
                logger.warning(f"No predictions in response: {result}")
                # Log the full response for debugging
                logger.warning(f"Full response text: {response.text[:1000]}")
                return None, "", ""
        else:
            logger.warning(
                f"Imagen API error {response.status_code}: {response.text[:500]}")
            return None, "", ""

    except Exception as e:
        logger.warning(f"Imagen generation failed: {e}", exc_info=True)
        return None, "", ""
