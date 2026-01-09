"""Image generation using Gemini only."""
import logging
from typing import Tuple, Optional
import requests
import config

logger = logging.getLogger(__name__)


def generate_featured_image(
    topic: str,
    brand_name: str = "",
    language: str = "nl"
) -> Tuple[Optional[bytes], str, str]:
    """
    Generate a featured image using Gemini only.

    Returns:
        Tuple of (image_bytes, mime_type, filename) or (None, "", "") on failure
    """
    return _try_gemini_image(topic)


def _try_gemini_image(topic: str) -> Tuple[Optional[bytes], str, str]:
    """Try Gemini Imagen API with correct structure."""
    try:
        prompt = f"""Create a professional, modern blog header image about: {topic}

Style: Clean, minimalist, abstract, high quality
Requirements:
- No text or logos
- Professional and visually appealing  
- Suitable for business blog featured image
- Modern color palette
- Landscape format ideal for blog header
- High resolution, 16:9 aspect ratio"""

        logger.info(f"Generating image with Imagen 4.0 for: {topic}")

        # Use correct Imagen API endpoint and structure from official docs
        url = "https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict"

        headers = {
            "x-goog-api-key": config.GEMINI_API_KEY,
            "Content-Type": "application/json"
        }

        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "16:9"
            }
        }

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
                    filename = f"featured-{topic[:30].replace(' ', '-').lower()}.png"
                    logger.info(
                        f"Imagen image generated successfully ({len(image_bytes)} bytes)")
                    return image_bytes, "image/png", filename
                else:
                    logger.warning(
                        f"Could not extract image from prediction: {prediction}")
                    return None, "", ""
            else:
                logger.warning(f"No predictions in response: {result}")
                return None, "", ""
        else:
            logger.warning(
                f"Imagen API error {response.status_code}: {response.text[:500]}")
            return None, "", ""

    except Exception as e:
        logger.warning(f"Imagen generation failed: {e}", exc_info=True)
        return None, "", ""
