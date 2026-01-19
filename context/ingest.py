"""Website content ingest orchestrator."""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from context.crawler import WebsiteCrawler
from context.extractor import ContentExtractor
from context.site_dna import refresh_site_dna
from db import get_db_connection, get_site
import json

logger = logging.getLogger(__name__)


def ingest_website(
    site_id: str,
    seed_urls: Optional[List[str]] = None,
    max_depth: int = 3,
    max_pages: int = 50
) -> Dict[str, Any]:
    """
    Ingest website content: crawl, extract, chunk, and generate Site DNA.
    
    Args:
        site_id: Site identifier
        seed_urls: URLs to start crawling from (defaults to site base URL)
        max_depth: Maximum crawl depth
        max_pages: Maximum pages to crawl
        
    Returns:
        Dictionary with ingest statistics
    """
    logger.info(f"Starting website ingest for site: {site_id}")
    
    # Get site info
    site = get_site(site_id)
    if not site:
        raise ValueError(f"Site not found: {site_id}")
    
    base_url = site["wp_base_url"]
    
    # Default seed URLs
    if seed_urls is None:
        seed_urls = [base_url]
    
    # Step 1: Crawl website
    logger.info("Step 1/4: Crawling website...")
    crawler = WebsiteCrawler(
        base_url=base_url,
        max_depth=max_depth,
        max_pages=max_pages
    )
    crawled_pages = crawler.crawl(seed_urls)
    logger.info(f"Crawled {len(crawled_pages)} pages")
    
    if len(crawled_pages) == 0:
        logger.warning(f"No pages crawled from {base_url}. Check if the site is accessible and doesn't block crawlers.")
        return {
            "site_id": site_id,
            "pages_crawled": 0,
            "pages_stored": 0,
            "chunks_stored": 0,
            "site_dna_generated": False,
            "error": "No pages could be crawled. The site may be unreachable, blocking crawlers, or all pages returned errors.",
            "completed_at": datetime.utcnow().isoformat()
        }
    
    # Step 2: Extract and chunk content
    logger.info("Step 2/4: Extracting and chunking content...")
    extractor = ContentExtractor(max_chunk_tokens=1000)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    pages_stored = 0
    chunks_stored = 0
    
    for page_data in crawled_pages:
        try:
            # Extract clean content
            extracted = extractor.extract_clean_text(
                html=page_data["html"],
                url=page_data["url"]
            )
            
            # Skip pages with no content
            if not extracted["clean_text"]:
                logger.debug(f"Skipping page with no content: {page_data['url']}")
                continue
            
            # Store page
            cursor.execute("""
                INSERT OR REPLACE INTO scraped_pages (
                    site_id, url, canonical_url, title, clean_text, headings_json,
                    status_code, fetched_at, content_hash, page_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                site_id,
                page_data["url"],
                page_data["canonical_url"],
                page_data["title"],
                extracted["clean_text"],
                json.dumps(extracted["headings"]),
                page_data["status_code"],
                page_data["fetched_at"],
                page_data["content_hash"],
                extracted["page_type"]
            ))
            
            page_id = cursor.lastrowid
            pages_stored += 1
            
            # Chunk and store chunks
            chunks = extractor.chunk_content(
                clean_text=extracted["clean_text"],
                headings=extracted["headings"],
                url=page_data["url"]
            )
            
            for chunk in chunks:
                cursor.execute("""
                    INSERT INTO page_chunks (
                        page_id, site_id, chunk_index, section_heading,
                        chunk_text, chunk_tokens, url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    page_id,
                    site_id,
                    chunk["chunk_index"],
                    chunk["section_heading"],
                    chunk["chunk_text"],
                    chunk["chunk_tokens"],
                    chunk["url"]
                ))
                chunks_stored += 1
        
        except Exception as e:
            logger.error(f"Error processing page {page_data['url']}: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    logger.info(f"Stored {pages_stored} pages and {chunks_stored} chunks")
    
    # Check if this looks like a JavaScript-rendered site
    if len(crawled_pages) > 0 and pages_stored == 0:
        logger.warning("⚠️ No content extracted - this might be a JavaScript-rendered site (SPA/React/Vue)")
        logger.warning("💡 These sites need a headless browser or manual content input")
    
    # Step 3: Generate Site DNA
    logger.info("Step 3/4: Generating Site DNA...")
    try:
        site_dna = refresh_site_dna(site_id)
        logger.info("Site DNA generated successfully")
    except Exception as e:
        logger.error(f"Error generating Site DNA: {e}")
        site_dna = None
    
    logger.info("Step 4/4: Ingest complete")
    
    return {
        "site_id": site_id,
        "pages_crawled": len(crawled_pages),
        "pages_stored": pages_stored,
        "chunks_stored": chunks_stored,
        "site_dna_generated": site_dna is not None,
        "completed_at": datetime.utcnow().isoformat()
    }


def get_ingest_stats(site_id: str) -> Dict[str, Any]:
    """Get ingest statistics for a site."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Count pages
    cursor.execute("""
        SELECT COUNT(*) as count, MAX(fetched_at) as last_fetch
        FROM scraped_pages
        WHERE site_id = ?
    """, (site_id,))
    pages_row = cursor.fetchone()
    
    # Count chunks
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM page_chunks
        WHERE site_id = ?
    """, (site_id,))
    chunks_row = cursor.fetchone()
    
    # Check Site DNA
    cursor.execute("""
        SELECT generated_at
        FROM site_dna
        WHERE site_id = ?
        ORDER BY generated_at DESC
        LIMIT 1
    """, (site_id,))
    dna_row = cursor.fetchone()
    
    conn.close()
    
    return {
        "site_id": site_id,
        "pages_count": pages_row["count"] if pages_row else 0,
        "last_crawl": pages_row["last_fetch"] if pages_row else None,
        "chunks_count": chunks_row["count"] if chunks_row else 0,
        "site_dna_generated_at": dna_row["generated_at"] if dna_row else None
    }
