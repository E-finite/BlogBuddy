"""Image generation and editing via Google Vertex AI Imagen and Gemini."""
import base64
import logging
import os
import json
import re
from typing import Tuple, Optional, Dict, Any

import requests
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.auth.exceptions import RefreshError
from google import genai
from openai import OpenAI
from src import config
from src.prompt_templates import load_prompt_template, render_prompt_template

logger = logging.getLogger(__name__)
_openai_client = OpenAI(api_key=config.OPENAI_API_KEY)

_VERTEX_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_VERTEX_AUTH_BROKEN = False
_VERTEX_AUTH_ERROR = ""

# Aspect ratios supported by Imagen
_IMAGEN_ASPECT_MAP = {
    "1:1": "1:1",
    "16:9": "16:9",
    "9:16": "9:16",
    "3:4": "3:4",
    "4:3": "4:3",
}

_TEXT_REQUEST_HINTS = (
    "text",
    "headline",
    "title",
    "caption",
    "quote",
    "slogan",
    "tagline",
    "typography",
    "poster",
    "flyer",
    "banner",
    "sign",
    "label",
)

_GEMINI_IMAGE_MODEL_ALIASES = {
    "gemini-3.0-pro-image-latest": "gemini-3-pro-image-preview",
    "gemini-3-pro-image-latest": "gemini-3-pro-image-preview",
    "gemini-3.0-pro-image-preview": "gemini-3-pro-image-preview",
    "gemini-2.0-flash-exp-image-generation": "gemini-2.5-flash-image",
    "gemini-2.0-flash-exp": "gemini-2.5-flash-image",
}


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
    Generate or edit a featured image.

    - Initial generation (no reference): Google Gemini 2.0 Flash (primary) → Imagen (fallback)
    - Regeneration with reference image + feedback: Google Imagen edit model on Vertex AI
    - Final fallback: DALL-E 3

    Returns:
        Tuple of (image_bytes, mime_type, filename, error_message)
    """
    if brand is None:
        brand = {}
    if image_settings is None:
        image_settings = {}
    if feedback_chain is None:
        feedback_chain = []

    translated_feedback_chain = _translate_feedback_chain_to_english(
        feedback_chain)

    # Build base prompt (without feedback)
    base_prompt, aspect_ratio, brand_colors, use_brand_colors, preset = _build_prompt_and_settings(
        topic=topic,
        brand=brand,
        image_settings=image_settings,
        feedback_chain=[],  # No feedback yet
    )

    # Build final prompt with feedback for generation
    prompt, _, _, _, _ = _build_prompt_and_settings(
        topic=topic,
        brand=brand,
        image_settings=image_settings,
        feedback_chain=translated_feedback_chain,
    )

    logger.info(f"Generating image variation {variation_index} for: {topic}")
    logger.info(
        f"Settings: preset={preset}, aspect_ratio={aspect_ratio}, "
        f"colors={brand_colors if use_brand_colors else 'default'}"
    )
    if feedback_chain:
        logger.info(f"Feedback chain: {feedback_chain}")
    if feedback_chain and translated_feedback_chain != feedback_chain:
        logger.info(
            f"Translated feedback chain (EN): {translated_feedback_chain}")

    if reference_image_bytes:
        # Preferred path: Gemini 3 Pro with reference image for high-fidelity editing
        logger.info("Reference image detected; trying Gemini image edit first")
        result = _try_gemini_generate(
            topic,
            prompt,
            aspect_ratio,
            variation_index,
            reference_image_bytes=reference_image_bytes,
            reference_image_mime_type=reference_image_mime_type,
        )
        if result[0]:
            return result
        logger.warning(
            f"Gemini image edit failed, falling back to Imagen image edit: {result[3]}")

        result = _try_imagen_image_edit(
            topic=topic,
            base_prompt=base_prompt,
            edit_prompt=prompt,
            variation_index=variation_index,
            reference_image_bytes=reference_image_bytes,
            reference_image_mime_type=reference_image_mime_type,
        )
        if result[0]:
            return result
        logger.warning(
            f"Imagen image edit failed, falling back to Gemini/Imagen generation: {result[3]}")

    # Initial generation (or last resort after edit failures): Gemini → Imagen → DALL-E 3
    result = _try_gemini_generate(topic, prompt, aspect_ratio, variation_index)
    if result[0]:
        return result

    logger.warning(
        f"Gemini generation failed, falling back to Imagen: {result[3]}")
    result = _try_imagen_generate(topic, prompt, aspect_ratio, variation_index)
    if result[0]:
        return result

    logger.warning(
        f"Imagen generation failed, falling back to DALL-E 3: {result[3]}")
    dalle_size = _aspect_to_dalle_size(aspect_ratio)
    return _try_dalle3_image(topic, prompt, dalle_size, variation_index)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt_and_settings(
    topic: str,
    brand: Dict[str, Any],
    image_settings: Dict[str, Any],
    feedback_chain: list[str],
) -> Tuple[str, str, list[str], bool, str]:
    """Build prompt and resolved image settings."""
    preset = image_settings.get("preset", "minimal-tech")
    aspect_ratio = image_settings.get("aspectRatio", "16:9")
    style_strength = image_settings.get("styleStrength", "medium")
    use_brand_colors = image_settings.get("useBrandColors", False)
    color_strictness = image_settings.get("colorStrictness", "medium")

    # Priority: custom brandColors from form > extracted from Site DNA
    custom_brand_colors = image_settings.get("brandColors", "")
    if custom_brand_colors:
        brand_colors = [c.strip()
                        for c in custom_brand_colors.split(",") if c.strip()]
    else:
        brand_colors = brand.get("colors", [])

    composition = image_settings.get("composition", "auto")
    lighting = image_settings.get("lighting", "soft-studio")
    negative_prompt = image_settings.get("negativePrompt", "")
    text_requested = _prompt_requests_visible_text(topic, feedback_chain)
    negative_prompt = _sanitize_negative_prompt(
        negative_prompt,
        allow_visible_text=text_requested,
    )

    style_presets = {
        "minimal-tech": "Clean, minimalist, modern tech aesthetic with geometric shapes",
        "bold-creative": "Bold, creative, vibrant with strong visual elements",
        "professional": "Professional, corporate, clean business aesthetic",
        "modern-gradient": "Modern gradient design with smooth color transitions",
        "flat-illustration": "Flat illustration style with simple shapes and colors",
    }
    style_desc = style_presets.get(preset, style_presets["minimal-tech"])

    lighting_desc = {
        "soft-studio": "soft studio lighting, even illumination",
        "natural": "natural daylight, soft shadows",
        "dramatic": "dramatic lighting with strong contrast",
        "backlit": "backlit subject with rim lighting",
    }.get(lighting, "soft studio lighting")

    composition_desc = {
        "auto": "",
        "centered": "centered hero composition",
        "left-whitespace": "subject on left with generous whitespace on right",
        "flat-lay": "flat lay top-down perspective",
        "isometric": "isometric 3D perspective",
    }.get(composition, "")

    # Detailed style strength descriptions with visual intensity hints
    strength_modifier = {
        "low": "subtle and understated",
        "medium": "balanced and expressive",
        "high": "bold, striking, and highly saturated",
    }.get(style_strength, "")

    # Color strictness instructions for brand color enforcement
    color_instruction = ""
    if use_brand_colors and brand_colors:
        color_hex_list = ", ".join(brand_colors)
        strictness_guidance = {
            "low": f"Use these colors as inspiration (not required): {color_hex_list}",
            "medium": f"Incorporate these brand colors moderately: {color_hex_list}",
            "high": f"Strictly adhere to this exact brand color palette: {color_hex_list}",
        }.get(color_strictness, f"Use these brand colors: {color_hex_list}")
        color_instruction = f"\n{strictness_guidance}"

    # Negative prompt handling
    negative_instruction = ""
    if negative_prompt:
        negative_instruction = f"\nAvoid: {negative_prompt}"

    text_instruction = _build_text_rendering_instruction(
        topic=topic,
        feedback_chain=feedback_chain,
    )

    prompt_template = load_prompt_template("image_gemini_base_prompt.txt")
    prompt = render_prompt_template(
        prompt_template,
        {
            "topic": topic,
            "style_desc": style_desc,
            "strength_modifier": strength_modifier,
            "composition_desc": composition_desc,
            "lighting_desc": lighting_desc,
            "text_instruction": text_instruction,
            "color_instruction": color_instruction,
            "negative_instruction": negative_instruction,
        },
    )

    if feedback_chain:
        feedback_template = load_prompt_template(
            "image_gemini_feedback_appendix.txt")

        # Track which feedbacks have been applied (all except the last one)
        if len(feedback_chain) > 1:
            previous_feedback = feedback_chain[:-1]
            previous_feedback_text = "\n".join(
                f"{i}. {feedback}" for i, feedback in enumerate(previous_feedback, 1)
            )
        else:
            previous_feedback_text = "(This is the first refinement)"

        # The current/latest feedback to focus on
        numbered_feedback = f"1. {feedback_chain[-1]}"

        prompt += "\n\n" + render_prompt_template(
            feedback_template,
            {
                "original_prompt": prompt,  # Include the base prompt for context
                "previous_feedback_applied": previous_feedback_text,
                "numbered_feedback_list": numbered_feedback
            },
        )

    return prompt, aspect_ratio, brand_colors, use_brand_colors, preset


def _extract_quoted_text(value: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r'["“”]([^"“”]{2,80})["“”]', value or "")
        if match.group(1).strip()
    ]


def _prompt_requests_visible_text(topic: str, feedback_chain: list[str]) -> bool:
    combined_parts = [topic, *feedback_chain]
    combined_text = " ".join(part for part in combined_parts if part).lower()
    if any(hint in combined_text for hint in _TEXT_REQUEST_HINTS):
        return True
    return bool(_extract_quoted_text(" ".join(part for part in combined_parts if part)))


def _sanitize_negative_prompt(negative_prompt: str, *, allow_visible_text: bool) -> str:
    if not negative_prompt or not allow_visible_text:
        return negative_prompt

    cleaned_terms = []
    for term in negative_prompt.split(","):
        normalized = term.strip()
        normalized_lower = normalized.lower()
        if not normalized:
            continue
        if "text overlay" in normalized_lower or "overlay text" in normalized_lower:
            continue
        cleaned_terms.append(normalized)
    return ", ".join(cleaned_terms)


def _build_text_rendering_instruction(topic: str, feedback_chain: list[str]) -> str:
    combined_parts = [topic, *feedback_chain]
    quoted_text = []
    for part in combined_parts:
        for item in _extract_quoted_text(part):
            if item not in quoted_text:
                quoted_text.append(item)

    lines = []
    if quoted_text:
        exact_text = ", ".join(f'"{item}"' for item in quoted_text)
        lines.append(
            f"If the image includes visible text, render this text exactly as written: {exact_text}."
        )
    else:
        lines.append(
            "If the image includes visible text, render the requested words exactly as specified."
        )

    lines.append(
        "Use a bold sans-serif font for short display text, with clean spacing, strong contrast, and consistent alignment."
    )
    lines.append("Ensure all text is legible and correctly spelt.")
    return "\n".join(lines)


def _translate_feedback_chain_to_english(feedback_chain: list[str]) -> list[str]:
    """Translate image edit feedback to English using OpenAI with graceful fallback."""
    if not feedback_chain:
        return []

    translation_model = getattr(
        config,
        "OPENAI_TRANSLATION_MODEL",
        getattr(config, "OPENAI_TEXT_MODEL", "gpt-4o"),
    )

    system_prompt = load_prompt_template(
        "image_feedback_translate_system_prompt.txt"
    )
    user_prompt_template = load_prompt_template(
        "image_feedback_translate_user_prompt.txt"
    )
    user_prompt = render_prompt_template(
        user_prompt_template,
        {"feedback_chain_json": json.dumps(
            feedback_chain, ensure_ascii=False)},
    )

    try:
        response = _openai_client.chat.completions.create(
            model=translation_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_completion_tokens=600,
        )

        raw_content = (response.choices[0].message.content or "{}").strip()
        payload = json.loads(raw_content)
        translations = payload.get("translations")

        if not isinstance(translations, list) or len(translations) != len(feedback_chain):
            logger.warning(
                "Feedback translation returned invalid shape; using original feedback chain"
            )
            return feedback_chain

        normalized_translations = []
        for i, translated in enumerate(translations):
            if isinstance(translated, str) and translated.strip():
                normalized_translations.append(translated.strip())
            else:
                normalized_translations.append(feedback_chain[i])

        return normalized_translations

    except Exception as e:
        logger.warning(
            f"Feedback translation failed, using original feedback chain: {e}"
        )
        return feedback_chain


# ---------------------------------------------------------------------------
# Google Gemini image generation
# ---------------------------------------------------------------------------

def _try_gemini_generate(
    topic: str,
    prompt: str,
    aspect_ratio: str,
    variation_index: int,
    reference_image_bytes: Optional[bytes] = None,
    reference_image_mime_type: Optional[str] = None,
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """Generate or edit an image with Google Gemini image models via the Gen AI SDK.

    When *reference_image_bytes* is provided the reference image is included in
    the request so Gemini treats the call as an image-edit / refinement rather
    than a fresh generation.
    """
    try:
        gemini_api_key = config.GEMINI_API_KEY
        if not gemini_api_key:
            return None, "", "", "GEMINI_API_KEY not configured"

        requested_model = getattr(
            config,
            "GEMINI_IMAGE_MODEL",
            "gemini-3-pro-image-preview",
        )
        gemini_model = _resolve_gemini_image_model(requested_model)
        image_size = _resolve_gemini_image_size(gemini_model)

        if gemini_model != requested_model:
            logger.info(
                f"Resolved Gemini image model alias: {requested_model} -> {gemini_model}"
            )

        logger.info(
            f"Sending request to Gemini API (model={gemini_model}, aspect_ratio={aspect_ratio})...")

        response_config = {
            "response_modalities": ["IMAGE"],
            "image_config": {
                "aspect_ratio": aspect_ratio,
            },
            "safety_settings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
            ],
        }
        if image_size:
            response_config["image_config"]["image_size"] = image_size

        from google.genai import types as genai_types

        contents: list = [prompt]
        if reference_image_bytes:
            ref_mime = reference_image_mime_type or "image/jpeg"
            contents.append(
                genai_types.Part.from_bytes(
                    data=reference_image_bytes,
                    mime_type=ref_mime,
                )
            )
            logger.info(
                f"Including reference image ({len(reference_image_bytes)} bytes, {ref_mime}) in Gemini request"
            )

        client = genai.Client(api_key=gemini_api_key)
        response = client.models.generate_content(
            model=gemini_model,
            contents=contents,
            config=response_config,
        )

        logger.info(f"Gemini API response received")

        image_bytes, mime_type = _extract_gemini_image_bytes(response)
        if not image_bytes:
            text_detail = _extract_gemini_text(response)
            detail_suffix = f" Response text: {text_detail}" if text_detail else ""
            return None, "", "", f"Gemini API returned no images.{detail_suffix}"

        out_ext = _extension_for_mime_type(mime_type)

        filename = f"featured-{topic[:30].replace(' ', '-').lower()}-var{variation_index}.{out_ext}"
        logger.info(
            f"Gemini generated successfully ({len(image_bytes)} bytes, {mime_type})"
        )
        return image_bytes, mime_type, filename, None

    except Exception as e:
        error_msg = f"Gemini generation error: {str(e)}"
        logger.warning(error_msg)
        return None, "", "", error_msg


def _resolve_gemini_image_model(model_name: str) -> str:
    normalized = (model_name or "").strip()
    if not normalized:
        return "gemini-3-pro-image-preview"
    return _GEMINI_IMAGE_MODEL_ALIASES.get(normalized, normalized)


def _resolve_gemini_image_size(model_name: str) -> Optional[str]:
    configured_size = (getattr(config, "GEMINI_IMAGE_SIZE", "") or "").strip()
    if configured_size:
        return configured_size
    if model_name == "gemini-3-pro-image-preview":
        return "2K"
    return None


def _response_parts(response: Any) -> list[Any]:
    if getattr(response, "parts", None):
        return list(response.parts)

    parts = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if getattr(content, "parts", None):
            parts.extend(content.parts)
    return parts


def _extract_gemini_image_bytes(response: Any) -> Tuple[Optional[bytes], str]:
    for part in _response_parts(response):
        if getattr(part, "thought", False):
            continue

        inline_data = getattr(part, "inline_data", None)
        if not inline_data:
            continue

        mime_type = getattr(inline_data, "mime_type", None) or getattr(
            inline_data, "mimetype", None) or "image/png"
        data = getattr(inline_data, "data", None)
        if isinstance(data, bytes) and data:
            return data, mime_type
        if isinstance(data, str) and data:
            return base64.b64decode(data), mime_type

    return None, ""


def _extract_gemini_text(response: Any) -> str:
    text_parts = []
    for part in _response_parts(response):
        if getattr(part, "thought", False):
            continue
        text = getattr(part, "text", None)
        if text:
            text_parts.append(text.strip())
    return " ".join(text_parts).strip()


# ---------------------------------------------------------------------------
# Google Imagen - fallback image generation
# ---------------------------------------------------------------------------

def _try_imagen_generate(
    topic: str,
    prompt: str,
    aspect_ratio: str,
    variation_index: int,
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """Generate an image with Google Imagen 3."""
    if _VERTEX_AUTH_BROKEN:
        return None, "", "", f"Vertex auth unavailable: {_VERTEX_AUTH_ERROR}"

    try:
        imagen_aspect = _IMAGEN_ASPECT_MAP.get(aspect_ratio, "16:9")
        imagen_model = getattr(config, "IMAGEN_MODEL",
                               "imagen-3.0-generate-002")
        url = _vertex_predict_url(imagen_model)
        headers = _vertex_auth_headers()
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": imagen_aspect,
                "safetyFilterLevel": "block_some",
                "personGeneration": "allow_adult",
            },
        }
        logger.info(
            f"Sending request to Vertex Imagen API (model={imagen_model}, aspectRatio={imagen_aspect})..."
        )
        response = requests.post(url, headers=headers,
                                 json=payload, timeout=120)
        logger.info(f"Imagen API response status: {response.status_code}")

        if response.status_code != 200:
            error_detail = response.text[:1000] if response.text else "No error details"
            error_msg = f"Imagen API error {response.status_code}"
            logger.error(f"{error_msg}: {error_detail}")
            try:
                error_json = response.json()
                if "error" in error_json:
                    msg = error_json["error"].get("message", "")
                    if msg:
                        error_msg = f"Imagen: {msg}"
            except Exception:
                pass
            return None, "", "", error_msg

        result = response.json()
        predictions = result.get("predictions") or []
        if not predictions:
            error_msg = "Imagen: no predictions in response"
            logger.warning(error_msg)
            return None, "", "", error_msg

        encoded = predictions[0].get("bytesBase64Encoded")
        if not encoded:
            error_msg = "Imagen: no bytesBase64Encoded in prediction"
            logger.warning(error_msg)
            return None, "", "", error_msg

        image_bytes = base64.b64decode(encoded)
        mime_type = predictions[0].get("mimeType", "image/png")
        ext = _extension_for_mime_type(mime_type)
        filename = f"featured-{topic[:30].replace(' ', '-').lower()}-var{variation_index}.{ext}"
        logger.info(
            f"Imagen image generated successfully ({len(image_bytes)} bytes, {mime_type})")
        return image_bytes, mime_type, filename, None

    except Exception as e:
        error_msg = f"Exception during Imagen generation: {str(e)}"
        if error_msg.startswith("Exception during Imagen generation: Vertex auth failed"):
            logger.warning(error_msg)
        else:
            logger.warning(error_msg, exc_info=True)
        return None, "", "", error_msg


# ---------------------------------------------------------------------------
# Imagen image editing - regeneration
# ---------------------------------------------------------------------------

def _try_imagen_image_edit(
    topic: str,
    base_prompt: str,
    edit_prompt: str,
    variation_index: int,
    reference_image_bytes: bytes,
    reference_image_mime_type: Optional[str],
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """Edit an existing image using Google Imagen 3 (inpainting/editing).

    Args:
        base_prompt: Original generation prompt (without edits)
        edit_prompt: Full prompt with edit instructions
    """
    if _VERTEX_AUTH_BROKEN:
        return None, "", "", f"Vertex auth unavailable: {_VERTEX_AUTH_ERROR}"

    try:
        configured_model = getattr(
            config, "IMAGEN_EDIT_MODEL", "imagen-3.0-capability-002")
        candidate_models = []
        for model_name in [configured_model, "imagen-3.0-capability-001"]:
            if model_name and model_name not in candidate_models:
                candidate_models.append(model_name)

        headers = _vertex_auth_headers()

        mime_type = reference_image_mime_type or "image/png"
        image_b64 = base64.b64encode(reference_image_bytes).decode("utf-8")

        # Official Imagen edit schema uses referenceImages with REFERENCE_TYPE_RAW
        # for mask-free editing.
        payload_variants = [
            {
                "instances": [
                    {
                        "prompt": edit_prompt,
                        "referenceImages": [
                            {
                                "referenceType": "REFERENCE_TYPE_RAW",
                                "referenceId": 1,
                                "referenceImage": {
                                    "bytesBase64Encoded": image_b64,
                                },
                            }
                        ],
                    }
                ],
                "parameters": {
                    "sampleCount": 1,
                    "safetySetting": "block_medium_and_above",
                    "personGeneration": "allow_adult",
                },
            },
            # Backward-compat variant for endpoints that still accept context_image.
            {
                "instances": [
                    {
                        "prompt": edit_prompt,
                        "image": {
                            "bytesBase64Encoded": image_b64,
                            "mimeType": mime_type,
                        },
                    }
                ],
                "parameters": {
                    "sampleCount": 1,
                    "safetySetting": "block_medium_and_above",
                    "personGeneration": "allow_adult",
                },
            },
        ]

        last_error = ""
        for edit_model in candidate_models:
            url = _vertex_predict_url(edit_model)
            logger.info(
                f"Sending request to Vertex Imagen image edit API "
                f"(model={edit_model}, reference={len(reference_image_bytes)} bytes)..."
            )
            response = None
            last_variant_error = ""
            for i, payload in enumerate(payload_variants, start=1):
                response = requests.post(url, headers=headers,
                                         json=payload, timeout=180)
                logger.info(
                    f"Imagen image edit API response status: {response.status_code} "
                    f"(payload_variant={i})")

                if response.status_code == 200:
                    break

                variant_detail = response.text[:1000] if response.text else "No error details"
                try:
                    variant_json = response.json()
                    variant_msg = variant_json.get(
                        "error", {}).get("message", "")
                    if variant_msg:
                        variant_detail = variant_msg
                except Exception:
                    pass

                last_variant_error = variant_detail

                # If the endpoint says context_image is required, do not continue this variant.
                if "context_image" in variant_detail:
                    continue

            if response is None:
                return None, "", "", "Imagen image edit: no response from API"

            if response.status_code == 200:
                result = response.json()
                predictions = result.get("predictions") or []
                if not predictions:
                    last_error = "Imagen image edit: no predictions in response"
                    logger.warning(last_error)
                    continue

                encoded = predictions[0].get("bytesBase64Encoded")
                if not encoded:
                    last_error = "Imagen image edit: no bytesBase64Encoded in prediction"
                    logger.warning(last_error)
                    continue

                image_bytes = base64.b64decode(encoded)
                out_mime_type = predictions[0].get("mimeType", "image/png")
                out_ext = _extension_for_mime_type(out_mime_type)

                filename = f"featured-{topic[:30].replace(' ', '-').lower()}-var{variation_index}.{out_ext}"
                logger.info(
                    f"Imagen image edit generated successfully ({len(image_bytes)} bytes, {out_mime_type}) "
                    f"using model={edit_model}"
                )
                return image_bytes, out_mime_type, filename, None

            error_detail = response.text[:1000] if response.text else "No error details"
            error_msg = f"Imagen image edit error {response.status_code}"
            try:
                error_json = response.json()
                if "error" in error_json:
                    msg = error_json["error"].get("message", "")
                    if msg:
                        error_msg = f"Imagen: {msg}"
            except Exception:
                pass

            if last_variant_error and "context_image" in last_variant_error and "context_image" not in error_msg:
                error_msg = f"{error_msg} (last variant hint: {last_variant_error})"

            # Retry another model only for "model unavailable" scenarios.
            unavailable = response.status_code == 404 and "unavailable" in error_msg.lower()
            if unavailable:
                logger.warning(
                    f"Imagen edit model unavailable ({edit_model}); trying next candidate. Details: {error_msg}"
                )
                last_error = error_msg
                continue

            logger.error(f"{error_msg}: {error_detail}")
            return None, "", "", error_msg

        return None, "", "", (last_error or "Imagen image edit failed for all candidate models")

    except Exception as e:
        error_msg = f"Exception during Imagen image edit: {str(e)}"
        if error_msg.startswith("Exception during Imagen image edit: Vertex auth failed"):
            logger.warning(error_msg)
        else:
            logger.warning(error_msg, exc_info=True)
        return None, "", "", error_msg


# ---------------------------------------------------------------------------
# DALL-E 3 - fallback
# ---------------------------------------------------------------------------

def _try_dalle3_image(
    topic: str,
    prompt: str,
    size: str,
    variation_index: int,
) -> Tuple[Optional[bytes], str, str, Optional[str]]:
    """Fallback: generate image with DALL-E 3."""
    try:
        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": "standard",
            "response_format": "b64_json",
        }

        logger.info(f"Sending request to DALL-E 3 API (size={size})...")
        response = requests.post(
            url, json=payload, headers=headers, timeout=120)
        logger.info(f"DALL-E 3 API response status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            data_items = result.get("data") or []
            if data_items and "b64_json" in data_items[0]:
                image_bytes = base64.b64decode(data_items[0]["b64_json"])
                filename = (
                    f"featured-{topic[:30].replace(' ', '-').lower()}-var{variation_index}.png"
                )
                logger.info(
                    f"DALL-E 3 image generated successfully ({len(image_bytes)} bytes)")
                return image_bytes, "image/png", filename, None
            error_msg = "DALL-E 3: no image data in response"
            logger.warning(error_msg)
            return None, "", "", error_msg

        error_msg = f"DALL-E 3 API error {response.status_code}"
        try:
            error_json = response.json()
            if "error" in error_json:
                if isinstance(error_json["error"], dict):
                    error_msg = f"OpenAI: {error_json['error'].get('message', error_msg)}"
                else:
                    error_msg = f"OpenAI: {str(error_json['error'])[:200]}"
        except Exception:
            pass
        logger.error(error_msg)
        return None, "", "", error_msg

    except Exception as e:
        error_msg = f"Exception during DALL-E 3 generation: {str(e)}"
        logger.warning(error_msg, exc_info=True)
        return None, "", "", error_msg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vertex_predict_url(model_name: str) -> str:
    return (
        f"https://{config.VERTEX_LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{config.VERTEX_PROJECT_ID}/locations/{config.VERTEX_LOCATION}/"
        f"publishers/google/models/{model_name}:predict"
    )


def _vertex_auth_headers() -> Dict[str, str]:
    global _VERTEX_AUTH_BROKEN, _VERTEX_AUTH_ERROR

    try:
        credentials, _ = google.auth.default(scopes=[_VERTEX_SCOPE])
        credentials.refresh(GoogleAuthRequest())
        _VERTEX_AUTH_BROKEN = False
        _VERTEX_AUTH_ERROR = ""
        return {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        }
    except RefreshError as e:
        error_text = str(e)
        if "Invalid JWT Signature" in error_text:
            key_hint = _diagnose_service_account_key_mismatch()
            msg = (
                "Vertex auth failed: Invalid JWT Signature. "
                "Controleer GOOGLE_APPLICATION_CREDENTIALS: gebruik een geldige service account key JSON "
                "(type=service_account), genereer eventueel een nieuwe key in GCP IAM, "
                "en check dat je systeemklok correct staat."
            )
            if key_hint:
                msg = f"{msg} {key_hint}"
            _VERTEX_AUTH_BROKEN = True
            _VERTEX_AUTH_ERROR = msg
            raise RuntimeError(msg) from e
        msg = f"Vertex auth failed: {error_text}"
        _VERTEX_AUTH_BROKEN = True
        _VERTEX_AUTH_ERROR = msg
        raise RuntimeError(msg) from e


def validate_vertex_auth_startup() -> None:
    """Validate Vertex credentials early so auth issues surface at startup."""
    _vertex_auth_headers()
    logger.info(
        "Vertex auth startup check OK "
        f"(project={config.VERTEX_PROJECT_ID}, location={config.VERTEX_LOCATION})"
    )


def _diagnose_service_account_key_mismatch() -> str:
    """Return a short diagnostic hint when local service-account key is no longer active."""
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not cred_path or not os.path.exists(cred_path):
        return ""

    try:
        with open(cred_path, "r", encoding="utf-8") as f:
            key_json = json.load(f)

        service_account_email = key_json.get("client_email", "")
        local_key_id = key_json.get("private_key_id", "")
        if not service_account_email or not local_key_id:
            return ""

        metadata_url = (
            "https://www.googleapis.com/robot/v1/metadata/x509/"
            f"{service_account_email}"
        )
        response = requests.get(metadata_url, timeout=15)
        if response.status_code != 200:
            return ""

        cert_map = response.json() if response.content else {}
        if not isinstance(cert_map, dict):
            return ""

        active_key_ids = list(cert_map.keys())
        if local_key_id not in active_key_ids:
            return (
                "Detected key mismatch: private_key_id uit je JSON staat niet tussen actieve Google keys. "
                "Maak een nieuwe service-account key en update GOOGLE_APPLICATION_CREDENTIALS."
            )

    except Exception:
        return ""

    return ""


def _aspect_to_dalle_size(aspect_ratio: str) -> str:
    return {
        "1:1": "1024x1024",
        "16:9": "1792x1024",
        "9:16": "1024x1792",
    }.get(aspect_ratio, "1792x1024")


def _extension_for_mime_type(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return "jpg"
    if mime_type == "image/webp":
        return "webp"
    return "png"
