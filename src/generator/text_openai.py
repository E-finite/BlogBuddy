"""OpenAI text generation using Responses API."""
import json
import logging
from typing import Dict, Any
from openai import OpenAI
from src import config

logger = logging.getLogger(__name__)
client = OpenAI(api_key=config.OPENAI_API_KEY)


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

    # NIEUW: Zorg dat deze variabelen beschikbaar zijn vanuit je formulier data
    # Als ze leeg zijn, vallen we terug op een generieke waarde
    current_angle = form_data.get('angle', 'Uitgebreide gids met tips')
    specific_question = form_data.get('customer_question', '')

    # Build website context section
    website_context_section = ""
    if website_context_bundle:
        website_context_section = f"""
### BRONMATERIAAL & HUISSTIJL:
{json.dumps(website_context_bundle, ensure_ascii=False, indent=2)}
REGELS:
1. Dit materiaal is leidend boven algemene kennis.
2. Gebruik de tone-of-voice keywords strikt.
3. Vermijd woorden uit de 'avoid_words' lijst.
"""

    # Build system prompt
    system_prompt = f"""
Je bent een senior contentstrateeg. Je schrijft long-form, diepgaande content voor {brand.get('name', 'het merk')} in het {language}.
Je doel is niet alleen informeren, maar de autoriteit op het onderwerp claimen door diepgang.

{website_context_section}

### 1. LENGTE & DIEPGANG (STRIKT)
Je schrijft een uitgebreid artikel (richtlijn: 600-800 woorden / 3500+ karakters).
Om dit te bereiken moet je de volgende structuur hanteren:
1. **Intro:** Pakkend, benoem het probleem, introduceer de oplossing.
2. **Kern:** Minimaal **4 secties (H2)**. Elke sectie moet diepgaand zijn (minimaal 2-3 alinea's per H2).
3. **Details:** Gebruik voorbeelden, scenario's of stappenplannen in elke sectie om body te geven.
4. **FAQ Sectie:** Eindig de body verplicht met een H2 getiteld "Veelgestelde vragen over [Onderwerp]" met daarin 3 relevante vragen en antwoorden.
5. **Conclusie:** Samenvatting en zachte CTA.

### 2. INVALSHOEK & UNIEKHEID
We willen GEEN generieke content die op elke andere website staat.
- **De Invalshoek:** Je schrijft dit artikel vanuit het type: "{current_angle}". Pas de structuur hierop aan.
- **Vermijd Herhaling:** Als je over algemene concepten schrijft, zoek dan altijd naar een specifieke nuance of een recent voorbeeld.
- **Diepgang:** Ga verder dan de basis. Leg niet alleen uit WAT iets is, maar ook HOE je het toepast en WAAROM het vaak misgaat.

### 3. SEO & GEO
- **Focus Keyword:** {seo.get('focusKeyword', '')} (Gebruik in Titel, Intro, minstens 1x H2, en verspreid in tekst).
- **Secondary Keywords:** {', '.join(seo.get('secondaryKeywords', []))}
- **Snippet-ready:** Zorg dat definities helder en direct na een kopje staan.

### 4. TONE OF VOICE
- Stijl: {', '.join(tone_of_voice.get('style', []))}
- Niveau: {audience.get('level', 'intermediate')}
- Schrijf actief en direct. Vermijd passieve zinnen.

### 5. FORMATTERING (HTML)
- Output moet pure HTML zijn in de JSON string.
- Gebruik <h2> voor hoofdsecties, <h3> voor subsecties.
- Gebruik <ul>/<ol> voor opsommingen (dit breekt de tekst en leest fijn).
- Gebruik <strong> om kernzinnen te benadrukken (max 1x per alinea).

### 6. JSON OUTPUT (STRIKT)
Geef ALLEEN de JSON terug.
{{
  "title": "...",
  "slug": "...",
  "excerpt": "...",
  "contentHtml": "...",
  "yoast": {{ "focuskw": "...", "seo_title": "...", "meta_desc": "..." }},
  "tags": [],
  "categories": []
}}
"""

    # Hier voegen we de specifieke sturing toe in de user prompt
    context_injection = ""
    if specific_question:
        context_injection = f"Behandel in dit artikel specifiek deze lezersvraag/situatie: '{specific_question}'."

    user_prompt = f"""
Schrijf het blogartikel over: "{topic}".

SPECIFIEKE OPDRACHT:
1. Invalshoek: Hanteer de stijl van een **{current_angle}**.
2. {context_injection}
3. Zorg voor voldoende lengte door veel voorbeelden te gebruiken.
4. Voeg aan het eind een FAQ sectie toe met 3 vragen.
5. Pijnpunten om te adresseren: {', '.join(audience.get('painPoints', []))}.
"""

    try:
        response = client.chat.completions.create(
            model=config.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=3000
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
        # Retry once with stricter instruction
        logger.info("Retrying with stricter JSON instruction...")
        retry_prompt = user_prompt + \
            "\n\nBELANGRIJK: Return ALLEEN geldige JSON, geen andere tekst."
        response = client.chat.completions.create(
            model=config.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": retry_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_tokens=3000
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        return result
