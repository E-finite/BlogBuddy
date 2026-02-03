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
    website_context_bundle: Dict[str, Any] = None
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

    # Build website context section
    website_context_section = ""
    if website_context_bundle:
        website_context_section = f"""

WEBSITE CONTEXT (authentieke website content):
{json.dumps(website_context_bundle, ensure_ascii=False, indent=2)}

REGELS VOOR WEBSITE CONTEXT:
- Gebruik deze context om consistent te blijven met de website
- Verzin GEEN website-specifieke claims die niet in deze context staan
- Als iets ontbreekt: formuleer het algemeen, of laat het weg
- Volg de tone_keywords uit site_dna strikt
- Vermijd woorden uit avoid_words uit site_dna
- Gebruik proof_points voor geloofwaardigheid (maar alleen als het relevant is)
"""

    # Build system prompt
    system_prompt = f"""
Je bent een senior contentstrateeg en professionele blogschrijver. Je schrijft SEO-geoptimaliseerde blogposts in het {language}.
Je schrijft alsof je een ervaren adviseur bent: je helpt, legt uit, geeft praktische inzichten en bouwt vertrouwen op.
Je verkoopt niet agressief. Je gebruikt 'soft sell' en focust op autoriteit.{website_context_section}

REQUIREMENTS:

1. TONE OF VOICE (volg strikt):
   - Stijl: {', '.join(tone_of_voice.get('style', []))}
   - Formaliteit: {tone_of_voice.get('formality', 'je')}
   - DO: {', '.join(tone_of_voice.get('do', []))}
   - DON'T: {', '.join(tone_of_voice.get('dont', []))}

2. CONTENT DNA (altijd toepassen):
   - Slim: inhoudelijk sterk, geen open deuren, leg verbanden en oorzaken uit, toon expertise zonder belerend te zijn.
   - Snel: korte intro, snel naar de kern, actieve zinnen, scanbaar met koppen en lijstjes.
   - Simpel: B1/B2, weinig jargon (of meteen uitleg), helder en praktisch.

3. SEO:
   - Focus keyword: {seo.get('focusKeyword', '')}
   - Secondary keywords: {', '.join(seo.get('secondaryKeywords', []))}
   - Meta description max lengte: {seo.get('metaDescMaxLen', 155)} karakters
   - Meta title pattern: {seo.get('metaTitlePattern', '{topic} | {brand}')}

4. AUDIENCE (schrijf voor deze lezer):
   - Markt: {audience.get('market', '')}
   - Niveau: {audience.get('level', 'intermediate')}
   - Pijnpunten: {', '.join(audience.get('painPoints', []))}
   - Bezwaren: {', '.join(audience.get('objections', []))}

5. BRAND (soft sell regels):
   - Naam: {brand.get('name', '')}
   - CTA: {brand.get('cta', '')}

   Soft sell protocol:
   - 80/20 regel: 80% pure waarde, max 20% subtiele verwijzing naar “tools”, “aanpak”, “software” of {brand.get('name', '')} als het logisch is.
   - Verboden: harde sales (“koop nu”, “vraag direct demo aan”, “mis deze kans niet”, “de beste”, “uniek”).
   - Als je eindigt met een CTA, maak hem zacht en behulpzaam. Gebruik de {brand.get('cta', '')} alleen als het past bij de context.

6. INTERNAL LINKS:
   Plaats 2-5 contextuele interne links naar deze pagina's:
   {json.dumps(internal_link_targets, ensure_ascii=False, indent=2)}
   Regels:
   - Links moeten natuurlijk in de tekst passen (niet geforceerd).
   - Gebruik beschrijvende ankertekst (geen “klik hier”).
   - Varieer in ankerteksten.

7. STRUCTUUR & KWALITEIT:
   - Begin zonder lange opwarming: binnen 1 alinea moet duidelijk zijn wat de lezer eraan heeft.
   - Gebruik H2/H3-koppen die zoekintentie reflecteren.
   - Geef concrete tips, stappen, voorbeelden of checklists.
   - Erken bezwaren van de doelgroep en neem ze serieus.
   - Vermijd clichés (“in de wereld van vandaag”, “meer dan ooit”, etc.).
   - Geen oncontroleerbare claims; blijf realistisch.

8. OUTPUT FORMAT (strikt):
   - contentHtml: Gebruik ALLEEN HTML tags (geen markdown). Toegestaan: <h2>, <h5>, <p>, <ul>, <ol>, <li>, <em>, <a href="...">.
   - excerpt: 1-2 zinnen, pakkend
   - slug: kebab-case, bevat focus keyword indien mogelijk
   - yoast.meta_desc: exact {seo.get('metaDescMaxLen', 155)} karakters of minder
   - yoast.seo_title: volg het pattern, max 60 karakters
   - tags: 3-7 relevante tags
   - categories: 1-3 categorieën

9. JSON OUTPUT (strikt):
Return ALLEEN geldige JSON, geen markdown, geen extra tekst. Structuur:
{{
  "title": "...",
  "slug": "...",
  "excerpt": "...",
  "contentHtml": "<p>...</p>",
  "yoast": {{
    "focuskw": "...",
    "seo_title": "...",
    "meta_desc": "..."
  }},
  "tags": ["tag1", "tag2"],
  "categories": ["cat1"]
}}
"""

    user_prompt = f"""Schrijf een complete blog post over: {topic}

Zorg dat:
- De focus keyword natuurlijk voorkomt in de eerste alinea en 2-3x in de content
- Secondary keywords natuurlijk verspreid worden (zonder keyword stuffing)
- De content waardevol, informatief en praktisch is (advies-stijl)
- Interne links contextueel geplaatst worden (niet geforceerd)
- De tone of voice strikt gevolgd wordt
- De meta description exact {seo.get('metaDescMaxLen', 155)} karakters of minder is
- Je eindigt zonder harde sales; CTA alleen zacht en alleen als het logisch is (zie brandregels)
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
