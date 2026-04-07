"""Site DNA extraction - generates brand identity from website content."""
import logging
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from src import config
from src.prompt_templates import load_prompt_template, render_prompt_template

logger = logging.getLogger(__name__)
client = OpenAI(api_key=config.OPENAI_API_KEY)


def generate_site_dna(
    pages: List[Dict[str, Any]],
    site_url: str,
    extracted_colors: List[str] = None
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
        extracted_colors: Pre-extracted hex color codes from HTML

    Returns:
        Dictionary with site DNA
    """
    logger.info(f"Generating Site DNA from {len(pages)} pages")

    # Select most important pages for analysis
    priority_pages = _select_priority_pages(pages)

    # Build context from pages
    pages_context = _build_pages_context(priority_pages)

    # Generate DNA with GPT using prompt templates
    system_prompt = load_prompt_template("site_dna_system_prompt.txt")

    extracted_colors_line = (
        f"GEEXTRAHEERDE KLEUREN UIT HTML: {', '.join(extracted_colors[:10])}"
        if extracted_colors
        else ""
    )
    brand_colors_rule = (
        "Gebruik de geextraheerde kleuren hierboven. Kies max 3 primaire/opvallende kleuren."
        if extracted_colors
        else "Lege array (geen kleuren beschikbaar)."
    )
    user_prompt_template = load_prompt_template("site_dna_user_prompt.txt")
    user_prompt = render_prompt_template(
        user_prompt_template,
        {
            "site_url": site_url,
            "pages_context": pages_context,
            "extracted_colors_line": extracted_colors_line,
            "brand_colors_rule": brand_colors_rule,
        },
    )

    try:
        response = client.chat.completions.create(
            model=config.OPENAI_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # Lower temperature for factual extraction
            max_completion_tokens=2000
        )
        content = response.choices[0].message.content
        dna = json.loads(content)

        # Validate structure
        required_fields = [
            "brand_name", "brand_colors", "brand_summary", "target_audiences", "pain_points",
            "solutions_themes", "tone_keywords", "avoid_words",
            "proof_points", "compliance_notes"
        ]

        for field in required_fields:
            if field not in dna:
                logger.warning(f"Missing field in Site DNA: {field}")
                if field in ["brand_name", "brand_summary"]:
                    dna[field] = ""
                else:
                    dna[field] = []

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
    selected_type_counts: Dict[str, int] = {}

    for page in sorted_pages:
        page_type = page.get("page_type", "page")

        # Always include landing, about, pricing if available
        if page_type in ["landing", "about", "pricing"]:
            selected.append(page)
            selected_type_counts[page_type] = selected_type_counts.get(page_type, 0) + 1
        # Include up to 3 service pages
        elif page_type == "service" and selected_type_counts.get("service", 0) < 3:
            selected.append(page)
            selected_type_counts[page_type] = selected_type_counts.get(page_type, 0) + 1
        # Include 1 FAQ if available
        elif page_type == "faq" and selected_type_counts.get("faq", 0) < 1:
            selected.append(page)
            selected_type_counts[page_type] = selected_type_counts.get(page_type, 0) + 1
        # Include up to 2 blogs
        elif page_type == "blog" and selected_type_counts.get("blog", 0) < 2:
            selected.append(page)
            selected_type_counts[page_type] = selected_type_counts.get(page_type, 0) + 1

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


def refresh_site_dna(site_id: str, site_type: str = 'wp', extracted_colors: List[str] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Refresh Site DNA for a site by re-analyzing scraped pages.

    Args:
        site_id: Site identifier
        site_type: Type of site ('wp' or 'context')
        extracted_colors: Pre-extracted color hex codes from HTML
        user_id: User ID for multi-tenant support

    Returns:
        Generated Site DNA dictionary
    """
    from src.db import get_db_connection
    from datetime import datetime

    logger.info(f"Refreshing Site DNA for site: {site_id} (type: {site_type})")

    # Get scraped pages from database
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT url, title, clean_text, page_type
        FROM scraped_pages
        WHERE site_id = %s AND site_type = %s
        ORDER BY 
            CASE page_type
                WHEN 'landing' THEN 1
                WHEN 'about' THEN 2
                WHEN 'service' THEN 3
                WHEN 'pricing' THEN 4
                WHEN 'faq' THEN 5
                ELSE 6
            END
    """, (site_id, site_type))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise ValueError(f"No scraped pages found for site {site_id}")

    pages = [dict(row) for row in rows]

    # Get site URL based on type
    if site_type == 'context':
        from src.db import get_context_site
        site = get_context_site(site_id)
        site_url = site["base_url"] if site else "unknown"
    else:
        from src.db import get_site
        site = get_site(site_id)
        site_url = site["wp_base_url"] if site else "unknown"

    # Generate DNA
    dna = generate_site_dna(pages, site_url, extracted_colors=extracted_colors)

    # Store in database
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.utcnow().isoformat()
    source_urls = [p["url"] for p in pages]

    # First delete old DNA if exists (we only keep latest)
    cursor.execute(
        "DELETE FROM site_dna WHERE site_id = %s AND site_type = %s", (site_id, site_type))

    cursor.execute("""
        INSERT INTO site_dna (
            site_id, user_id, site_type, brand_name, brand_colors_json, brand_summary, target_audiences_json, pain_points_json,
            solutions_themes_json, tone_keywords_json, avoid_words_json,
            proof_points_json, compliance_notes_json, generated_at, source_pages_json
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        site_id,
        user_id,
        site_type,
        dna.get("brand_name", ""),
        json.dumps(dna.get("brand_colors", [])),
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


def get_site_dna(site_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Get the latest Site DNA for a site.

    Args:
        site_id: Site identifier
        user_id: Optional user ID for multi-tenant filtering

    Returns:
        Site DNA dictionary or None if not found
    """
    from src.db import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if user_id is not None:
        # Filter by user_id for multi-tenant
        cursor.execute("""
            SELECT *
            FROM site_dna
            WHERE site_id = %s AND (user_id = %s OR user_id IS NULL)
            ORDER BY generated_at DESC
            LIMIT 1
        """, (site_id, user_id))
    else:
        # Backwards compatible - no user filter
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
        "brand_name": row.get("brand_name", ""),
        "brand_colors": json.loads(row.get("brand_colors_json", "[]")) if row.get("brand_colors_json") else [],
        "brand_summary": row["brand_summary"],
        "target_audiences": json.loads(row["target_audiences_json"]),
        "pain_points": json.loads(row["pain_points_json"]),
        "solutions_themes": json.loads(row["solutions_themes_json"]),
        "tone_keywords": json.loads(row["tone_keywords_json"]),
        "avoid_words": json.loads(row["avoid_words_json"]),
        "proof_points": json.loads(row["proof_points_json"]),
        "compliance_notes": json.loads(row["compliance_notes_json"]),
        "generated_at": row["generated_at"].isoformat() if row["generated_at"] else None
    }
