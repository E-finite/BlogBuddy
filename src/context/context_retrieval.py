"""Context retrieval - selects relevant snippets for blog generation."""
import logging
import json
from typing import List, Dict, Any, Optional
from collections import Counter
import re

logger = logging.getLogger(__name__)


class ContextRetriever:
    """Retrieves relevant website context for blog generation."""

    def __init__(self, site_id: str):
        """
        Initialize retriever for a site.

        Args:
            site_id: Site identifier
        """
        self.site_id = site_id

    def get_context_bundle(
        self,
        topic: str,
        seo: Dict[str, Any],
        audience: Dict[str, Any],
        max_snippets: int = 6
    ) -> Dict[str, Any]:
        """
        Build context bundle for blog generation.

        Args:
            topic: Blog topic
            seo: SEO configuration with focusKeyword, secondaryKeywords
            audience: Audience configuration with market, painPoints
            max_snippets: Maximum number of snippets to return

        Returns:
            Context bundle with site_dna and relevant_snippets
        """
        from context.site_dna import get_site_dna

        logger.info(f"Building context bundle for topic: {topic}")

        # Get Site DNA
        site_dna = get_site_dna(self.site_id)
        if not site_dna:
            logger.warning(f"No Site DNA found for site {self.site_id}")
            site_dna = {}

        # Get relevant chunks
        chunks = self._get_relevant_chunks(topic, seo, audience, max_snippets)

        # Build snippets
        snippets = []
        for chunk in chunks:
            snippets.append({
                "url": chunk["url"],
                "heading": chunk["section_heading"],
                "excerpt": self._truncate_excerpt(chunk["chunk_text"], 800)
            })

        return {
            "site_dna": site_dna,
            "relevant_snippets": snippets
        }

    def _get_relevant_chunks(
        self,
        topic: str,
        seo: Dict[str, Any],
        audience: Dict[str, Any],
        max_chunks: int
    ) -> List[Dict[str, Any]]:
        """Get relevant chunks from database using keyword scoring."""
        from db import get_db_connection

        # Build query keywords
        query_keywords = self._extract_keywords(topic, seo, audience)

        # Get all chunks
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                pc.*,
                sp.url,
                sp.page_type
            FROM page_chunks pc
            JOIN scraped_pages sp ON pc.page_id = sp.id
            WHERE pc.site_id = %s
        """, (self.site_id,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.warning(f"No chunks found for site {self.site_id}")
            return []

        chunks = rows  # rows are already dictionaries with dictionary=True cursor

        # Score chunks
        scored_chunks = []
        for chunk in chunks:
            score = self._score_chunk(chunk, query_keywords)
            if score > 0:
                chunk["relevance_score"] = score
                scored_chunks.append(chunk)

        # Sort by score and take top chunks
        scored_chunks.sort(key=lambda c: c["relevance_score"], reverse=True)
        top_chunks = scored_chunks[:max_chunks]

        logger.info(
            f"Selected {len(top_chunks)} relevant chunks (from {len(chunks)} total)")

        return top_chunks

    def _extract_keywords(
        self,
        topic: str,
        seo: Dict[str, Any],
        audience: Dict[str, Any]
    ) -> List[str]:
        """Extract keywords from topic, SEO, and audience."""
        keywords = []

        # Add topic words
        keywords.extend(self._tokenize(topic))

        # Add SEO keywords
        focus_kw = seo.get("focusKeyword", "")
        if focus_kw:
            keywords.extend(self._tokenize(focus_kw))

        secondary_kws = seo.get("secondaryKeywords", [])
        for kw in secondary_kws:
            keywords.extend(self._tokenize(kw))

        # Add audience pain points
        pain_points = audience.get("painPoints", [])
        for pain in pain_points:
            keywords.extend(self._tokenize(pain))

        # Deduplicate and lowercase
        keywords = list(set(kw.lower() for kw in keywords))

        # Remove stopwords
        stopwords = {
            "de", "het", "een", "en", "van", "in", "op", "voor", "met", "aan", "door",
            "bij", "naar", "te", "om", "over", "dat", "dit", "die", "deze", "is", "zijn",
            "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "by",
            "at", "from", "as", "into", "this", "that", "it", "be", "are", "was", "were"
        }
        keywords = [
            kw for kw in keywords if kw not in stopwords and len(kw) > 2]

        return keywords

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Remove punctuation and split
        text = re.sub(r'[^\w\s]', ' ', text)
        return text.split()

    def _score_chunk(self, chunk: Dict[str, Any], query_keywords: List[str]) -> float:
        """Score a chunk's relevance to the query."""
        score = 0.0

        chunk_text = chunk.get("chunk_text", "").lower()
        section_heading = chunk.get("section_heading", "").lower()
        page_type = chunk.get("page_type", "")

        # Keyword overlap scoring
        chunk_words = set(self._tokenize(chunk_text))
        heading_words = set(self._tokenize(section_heading))

        for keyword in query_keywords:
            # Exact match in heading (high value)
            if keyword in section_heading:
                score += 3.0

            # Exact match in text
            if keyword in chunk_text:
                score += 1.0

            # Word-level match in heading
            if keyword in heading_words:
                score += 2.0

            # Word-level match in text
            if keyword in chunk_words:
                score += 0.5

        # Boost for certain page types
        page_type_boost = {
            "service": 1.5,
            "landing": 1.3,
            "faq": 1.2,
            "about": 1.1,
            "pricing": 1.0,
            "blog": 0.8,
            "page": 0.9
        }
        score *= page_type_boost.get(page_type, 1.0)

        # Penalize very short chunks
        if len(chunk_text) < 100:
            score *= 0.5

        return score

    def _truncate_excerpt(self, text: str, max_chars: int) -> str:
        """Truncate text to max_chars, breaking at sentence boundary."""
        if len(text) <= max_chars:
            return text

        # Find last sentence boundary before max_chars
        truncated = text[:max_chars]
        last_period = truncated.rfind(".")
        last_question = truncated.rfind("?")
        last_exclamation = truncated.rfind("!")

        last_sentence_end = max(last_period, last_question, last_exclamation)

        if last_sentence_end > 0:
            return text[:last_sentence_end + 1]
        else:
            # No sentence boundary, just truncate
            return truncated.rstrip() + "..."


def build_context_bundle(
    site_id: str,
    topic: str,
    seo: Dict[str, Any],
    audience: Dict[str, Any],
    max_snippets: int = 6
) -> Dict[str, Any]:
    """
    Convenience function to build context bundle.

    Args:
        site_id: Site identifier
        topic: Blog topic
        seo: SEO configuration
        audience: Audience configuration
        max_snippets: Maximum snippets to return

    Returns:
        Context bundle dictionary
    """
    retriever = ContextRetriever(site_id)
    return retriever.get_context_bundle(topic, seo, audience, max_snippets)
