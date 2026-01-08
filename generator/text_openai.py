"""OpenAI text generation using Responses API."""
import json
import logging
from typing import Dict, Any
from openai import OpenAI
import config

logger = logging.getLogger(__name__)
client = OpenAI(api_key=config.OPENAI_API_KEY)


def generate_post_content(
    topic: str,
    audience: Dict[str, Any],
    tone_of_voice: Dict[str, Any],
    seo: Dict[str, Any],
    brand: Dict[str, Any],
    language: str = "nl",
    internal_link_targets: list = None
) -> Dict[str, Any]:
    """
    Generate blog post content using OpenAI Responses API.
    
    Returns:
        Dict with keys: title, slug, excerpt, contentHtml, yoast (focuskw, seo_title, meta_desc), tags, categories
    """
    if internal_link_targets is None:
        internal_link_targets = []
    
    # Build system prompt
    system_prompt = f"""Je bent een professionele blog content schrijver. Je schrijft SEO-geoptimaliseerde blog posts in het {language}.

REQUIREMENTS:
1. TONE OF VOICE:
   - Stijl: {', '.join(tone_of_voice.get('style', []))}
   - Formaliteit: {tone_of_voice.get('formality', 'je')}
   - DO: {', '.join(tone_of_voice.get('do', []))}
   - DON'T: {', '.join(tone_of_voice.get('dont', []))}

2. SEO:
   - Focus keyword: {seo.get('focusKeyword', '')}
   - Secondary keywords: {', '.join(seo.get('secondaryKeywords', []))}
   - Meta description max lengte: {seo.get('metaDescMaxLen', 155)} karakters
   - Meta title pattern: {seo.get('metaTitlePattern', '{topic} | {brand}')}

3. AUDIENCE:
   - Markt: {audience.get('market', '')}
   - Niveau: {audience.get('level', 'intermediate')}
   - Pijnpunten: {', '.join(audience.get('painPoints', []))}
   - Bezwaren: {', '.join(audience.get('objections', []))}

4. BRAND:
   - Naam: {brand.get('name', '')}
   - CTA: {brand.get('cta', '')}

5. INTERNAL LINKS:
   Plaats 2-5 contextuele interne links naar deze pagina's:
   {json.dumps(internal_link_targets, ensure_ascii=False, indent=2)}

6. OUTPUT FORMAT:
   - contentHtml: Gebruik ALLEEN HTML tags (geen markdown). Gebruik <h2>, <h3>, <p>, <ul>, <ol>, <li>, <strong>, <em>, <a href="...">.
   - excerpt: 1-2 zinnen, pakkend
   - slug: kebab-case, bevat focus keyword indien mogelijk
   - yoast.meta_desc: exact {seo.get('metaDescMaxLen', 155)} karakters of minder
   - yoast.seo_title: volg het pattern, max 60 karakters
   - tags: 3-7 relevante tags
   - categories: 1-3 categorieën

7. JSON OUTPUT:
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
- De content waardevol, informatief en actiegericht is
- Interne links contextueel geplaatst worden (niet geforceerd)
- De tone of voice strikt gevolgd wordt
- De meta description exact {seo.get('metaDescMaxLen', 155)} karakters of minder is
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
            result["yoast"]["meta_desc"] = result["yoast"]["meta_desc"][:seo.get("metaDescMaxLen", 155)].rstrip()
        
        # Ensure slug is kebab-case
        result["slug"] = result["slug"].lower().replace(" ", "-").replace("_", "-")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from OpenAI: {e}")
        # Retry once with stricter instruction
        logger.info("Retrying with stricter JSON instruction...")
        retry_prompt = user_prompt + "\n\nBELANGRIJK: Return ALLEEN geldige JSON, geen andere tekst."
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
