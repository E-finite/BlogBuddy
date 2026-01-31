"""Site DNA extraction - generates brand identity from website content."""
import logging
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
import config

logger = logging.getLogger(__name__)
client = OpenAI(api_key=config.OPENAI_API_KEY)


def generate_site_dna(
    pages: List[Dict[str, Any]],
    site_url: str
) -> Dict[str, Any]:
    """
    Generate site DNA from scraped pages.

    Analyzes the website content to extract:
    - Brand summary and positioning
    - Target audiences
    - Pain points addressed
    - Solutions/themes
    - Tone of voice keywords
    - Words to avoid
    - Proof points (factual claims from site)
    - Compliance notes

    Args:
        pages: List of page dictionaries with clean_text, title, url, page_type
        site_url: Base URL of the site

    Returns:
        Dictionary with site DNA
    """
    logger.info(f"Generating Site DNA from {len(pages)} pages")

    # Select most important pages for analysis
    priority_pages = _select_priority_pages(pages)

    # Build context from pages
    pages_context = _build_pages_context(priority_pages)

    # Generate DNA with GPT
    system_prompt = """Je bent een expert brand analyst en content strategist.
Je analyseert website content en extraheert de kern-identiteit, positionering, en tone of voice.

Je taak is om een "Site DNA" te creëren: een compacte maar complete beschrijving van:
- Wat de organisatie doet en belooft
- Voor wie (doelgroepen)
- Welke problemen ze oplossen
- Hoe ze communiceren (tone of voice)
- Wat wel/niet te zeggen (woordenlijst)
- Feitelijke bewijspunten die op de site staan

BELANGRIJK:
- Gebruik alleen informatie die LETTERLIJK op de website staat
- Verzin geen claims, features, of cijfers die er niet staan
- Wees specifiek maar compact
- Focus op wat uniek of karakteristiek is
- Let op tone of voice: formeel/informeel, zakelijk/toegankelijk, etc.
"""

    user_prompt = f"""Analyseer deze website content en genereer een Site DNA.

WEBSITE: {site_url}

PAGINA'S:
{pages_context}

Genereer een JSON object met deze structuur:
{{
  "brand_summary": "Korte beschrijving (2-3 zinnen) van wat de organisatie doet en belooft",
  "target_audiences": ["primaire doelgroep 1", "doelgroep 2", ...],
  "pain_points": ["pijnpunt/probleem dat klanten hebben", ...],
  "solutions_themes": ["kernoplossing/thema 1", "thema 2", ...],
  "tone_keywords": ["stijlwoord 1", "stijlwoord 2", ...],
  "avoid_words": ["woord om te vermijden", ...],
  "proof_points": ["feitelijke claim die letterlijk op de site staat", ...],
  "compliance_notes": ["disclaimer of randvoorwaarde die de site noemt", ...]
}}

Regels:
- tone_keywords: 5-10 woorden die de schrijfstijl beschrijven (bijv. "nuchter", "praktisch", "toegankelijk")
- avoid_words: overdreven termen die NIET passen bij de tone (bijv. "revolutionair", "uniek", "beste")
- proof_points: alleen claims die je letterlijk terug kunt vinden in de content (geen aannames)
- compliance_notes: juridische disclaimers, beperkingen, voorwaarden die worden genoemd

Wees kritisch en accuraat. Geen fantasie.
"""

    try:
        response = client.chat.completions.create(
            model=config.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # Lower temperature for factual extraction
            max_tokens=2000
        )

        content = response.choices[0].message.content
        dna = json.loads(content)

        # Validate structure
        required_fields = [
            "brand_summary", "target_audiences", "pain_points",
            "solutions_themes", "tone_keywords", "avoid_words",
            "proof_points", "compliance_notes"
        ]

        for field in required_fields:
            if field not in dna:
                logger.warning(f"Missing field in Site DNA: {field}")
                dna[field] = [] if field != "brand_summary" else ""

        logger.info("Site DNA generated successfully")
        return dna

    except Exception as e:
        logger.error(f"Error generating Site DNA: {e}")
        raise


def _select_priority_pages(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Select the most important pages for DNA extraction."""
    priority_order = ["landing", "about",
                      "service", "pricing", "faq", "blog", "page"]

    # Sort pages by priority
    def page_priority(page):
        page_type = page.get("page_type", "page")
        try:
            return priority_order.index(page_type)
        except ValueError:
            return len(priority_order)

    sorted_pages = sorted(pages, key=page_priority)

    # Take up to 15 pages, prioritizing different types
    selected = []
    selected_types = set()

    for page in sorted_pages:
        page_type = page.get("page_type", "page")

        # Always include landing, about, pricing if available
        if page_type in ["landing", "about", "pricing"]:
            selected.append(page)
            selected_types.add(page_type)
        # Include up to 3 service pages
        elif page_type == "service" and selected_types.count("service") < 3:
            selected.append(page)
            selected_types.add(page_type)
        # Include 1 FAQ if available
        elif page_type == "faq" and "faq" not in selected_types:
            selected.append(page)
            selected_types.add("faq")
        # Include up to 2 blogs
        elif page_type == "blog" and list(selected_types).count("blog") < 2:
            selected.append(page)
            selected_types.add("blog")

        if len(selected) >= 15:
            break

    logger.info(f"Selected {len(selected)} priority pages for DNA extraction")
    return selected


def _build_pages_context(pages: List[Dict[str, Any]]) -> str:
    """Build a compact context string from pages."""
    context_parts = []

    for i, page in enumerate(pages, 1):
        title = page.get("title", "Untitled")
        url = page.get("url", "")
        page_type = page.get("page_type", "page")
        clean_text = page.get("clean_text", "")

        # Truncate very long pages
        if len(clean_text) > 3000:
            clean_text = clean_text[:3000] + "..."

        context_parts.append(f"""--- PAGE {i}: {title} ({page_type}) ---
URL: {url}
CONTENT:
{clean_text}
""")

    return "\n\n".join(context_parts)


def refresh_site_dna(site_id: str) -> Dict[str, Any]:
    """
    Refresh Site DNA for a site by re-analyzing scraped pages.

    Args:
        site_id: Site identifier

    Returns:
        Generated Site DNA dictionary
    """
    from db import get_db_connection
    from datetime import datetime

    logger.info(f"Refreshing Site DNA for site: {site_id}")

    # Get scraped pages from database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT url, title, clean_text, page_type
        FROM scraped_pages
        WHERE site_id = %s
        ORDER BY 
            CASE page_type
                WHEN 'landing' THEN 1
                WHEN 'about' THEN 2
                WHEN 'service' THEN 3
                WHEN 'pricing' THEN 4
                WHEN 'faq' THEN 5
                ELSE 6
            END
    """, (site_id,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise ValueError(f"No scraped pages found for site {site_id}")

    pages = [dict(row) for row in rows]

    # Get site URL
    from db import get_site
    site = get_site(site_id)
    site_url = site["wp_base_url"] if site else "unknown"

    # Generate DNA
    dna = generate_site_dna(pages, site_url)

    # Store in database
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.utcnow().isoformat()
    source_urls = [p["url"] for p in pages]

    # First delete old DNA if exists (we only keep latest)
    cursor.execute("DELETE FROM site_dna WHERE site_id = %s", (site_id,))

    cursor.execute("""
        INSERT INTO site_dna (
            site_id, brand_summary, target_audiences_json, pain_points_json,
            solutions_themes_json, tone_keywords_json, avoid_words_json,
            proof_points_json, compliance_notes_json, generated_at, source_pages_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        site_id,
        dna.get("brand_summary", ""),
        json.dumps(dna.get("target_audiences", [])),
        json.dumps(dna.get("pain_points", [])),
        json.dumps(dna.get("solutions_themes", [])),
        json.dumps(dna.get("tone_keywords", [])),
        json.dumps(dna.get("avoid_words", [])),
        json.dumps(dna.get("proof_points", [])),
        json.dumps(dna.get("compliance_notes", [])),
        now,
        json.dumps(source_urls)
    ))

    conn.commit()
    conn.close()

    logger.info(f"Site DNA stored for site: {site_id}")
    return dna


def get_site_dna(site_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the latest Site DNA for a site.

    Args:
        site_id: Site identifier

    Returns:
        Site DNA dictionary or None if not found
    """
    from db import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM site_dna
        WHERE site_id = %s
        ORDER BY generated_at DESC
        LIMIT 1
    """, (site_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "brand_summary": row["brand_summary"],
        "target_audiences": json.loads(row["target_audiences_json"]),
        "pain_points": json.loads(row["pain_points_json"]),
        "solutions_themes": json.loads(row["solutions_themes_json"]),
        "tone_keywords": json.loads(row["tone_keywords_json"]),
        "avoid_words": json.loads(row["avoid_words_json"]),
        "proof_points": json.loads(row["proof_points_json"]),
        "compliance_notes": json.loads(row["compliance_notes_json"]),
        "generated_at": row["generated_at"]
    }
