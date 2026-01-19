"""Content extraction and chunking from HTML."""
import logging
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import trafilatura

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extracts clean content from HTML and chunks it."""
    
    def __init__(self, max_chunk_tokens: int = 1000):
        """
        Initialize extractor.
        
        Args:
            max_chunk_tokens: Maximum tokens per chunk (approximate)
        """
        self.max_chunk_tokens = max_chunk_tokens
        # Rough estimate: 1 token ~= 4 characters for Dutch/English
        self.max_chunk_chars = max_chunk_tokens * 4
    
    def extract_clean_text(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract clean text from HTML using trafilatura.
        
        Args:
            html: Raw HTML content
            url: Page URL for context
            
        Returns:
            Dictionary with clean_text, headings, and page_type
        """
        try:
            # Debug: log HTML size
            logger.info(f"Processing HTML from {url}: {len(html)} bytes")
            if len(html) < 5000:
                logger.warning(f"HTML is suspiciously small ({len(html)} bytes)")
            
            # Use trafilatura for main content extraction
            clean_text = trafilatura.extract(
                html,
                include_links=False,
                include_images=False,
                include_tables=False,
                no_fallback=False,
                favor_precision=False,  # Less precision, more content
                deduplicate=True
            )
            
            # Parse HTML for headings structure
            soup = BeautifulSoup(html, "html.parser")
            headings = self._extract_headings(soup)
            
            # Fallback: if trafilatura fails, use BeautifulSoup
            if not clean_text:
                logger.warning(f"Trafilatura failed for {url}, using BeautifulSoup fallback")
                clean_text = self._fallback_extraction(soup)
            
            if not clean_text:
                logger.warning(f"No content extracted from {url}")
                return {
                    "clean_text": "",
                    "headings": [],
                    "page_type": "unknown"
                }
            
            # Guess page type
            page_type = self._guess_page_type(url, soup, headings)
            
            return {
                "clean_text": clean_text,
                "headings": headings,
                "page_type": page_type
            }
        
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return {
                "clean_text": "",
                "headings": [],
                "page_type": "unknown"
            }
    
    def _fallback_extraction(self, soup: BeautifulSoup) -> str:
        """Fallback extraction using BeautifulSoup when trafilatura fails."""
        # Debug: check what's in the HTML
        logger.info(f"HTML structure - title: {soup.title.string if soup.title else 'None'}")
        logger.info(f"HTML structure - body length: {len(soup.body.get_text()) if soup.body else 0}")
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript']):
            element.decompose()
        
        # Try common content containers
        content_selectors = [
            'main',
            'article',
            '[role="main"]',
            '.content',
            '.main-content',
            '#content',
            '#main',
            '.post-content',
            '.entry-content',
            'body'
        ]
        
        content_text = ""
        for selector in content_selectors:
            container = soup.select_one(selector)
            if container:
                # Get all text, preserving paragraph structure
                paragraphs = []
                for p in container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'li', 'div']):
                    text = p.get_text(strip=True)
                    # Be less strict - accept shorter text
                    if text and len(text) > 10 and not self._is_likely_noise(text):
                        paragraphs.append(text)
                
                content_text = "\n\n".join(paragraphs)
                logger.info(f"Selector '{selector}' found {len(paragraphs)} text blocks, {len(content_text)} chars")
                if len(content_text) > 100:  # Lower threshold
                    break
        
        # If still no content, try body directly
        if not content_text or len(content_text) < 100:
            logger.info("Trying body fallback")
            body = soup.find('body')
            if body:
                # Get visible text
                text = body.get_text(separator='\n', strip=True)
                # Clean up multiple newlines
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                # Filter out very short lines (likely nav/menu items)
                content_lines = [line for line in lines if len(line) > 15]
                content_text = "\n\n".join(content_lines)
                logger.info(f"Body extraction found {len(content_lines)} lines, {len(content_text)} chars")
        
        return content_text
    
    def _is_likely_noise(self, text: str) -> bool:
        """Check if text is likely navigation or boilerplate."""
        noise_patterns = [
            'cookie', 'privacy', 'menu', 'navigation', 'skip to',
            'all rights reserved', 'copyright', '©', 'follow us'
        ]
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in noise_patterns)
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract heading structure from HTML."""
        headings = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            if text:
                headings.append({
                    "level": tag.name,
                    "text": text
                })
        return headings
    
    def _guess_page_type(self, url: str, soup: BeautifulSoup, headings: List[Dict]) -> str:
        """Guess the page type based on URL and content."""
        url_lower = url.lower()
        
        # Check URL patterns
        if any(pattern in url_lower for pattern in ["/blog/", "/nieuws/", "/artikel/"]):
            return "blog"
        if any(pattern in url_lower for pattern in ["/dienst", "/service", "/product"]):
            return "service"
        if "pricing" in url_lower or "prijs" in url_lower or "tarief" in url_lower:
            return "pricing"
        if "about" in url_lower or "over-ons" in url_lower or "team" in url_lower:
            return "about"
        if "contact" in url_lower:
            return "contact"
        if any(pattern in url_lower for pattern in ["faq", "vraag", "question"]):
            return "faq"
        
        # Check if it's the homepage
        parsed_path = url.split("?")[0].rstrip("/")
        if parsed_path.count("/") <= 3:  # e.g., https://example.com or https://example.com/nl
            return "landing"
        
        # Check content indicators
        body_classes = soup.find("body")
        if body_classes:
            classes = body_classes.get("class", [])
            if any("home" in c for c in classes):
                return "landing"
            if any("single" in c or "post" in c for c in classes):
                return "blog"
        
        return "page"
    
    def chunk_content(
        self,
        clean_text: str,
        headings: List[Dict[str, str]],
        url: str
    ) -> List[Dict[str, Any]]:
        """
        Chunk content into smaller pieces for retrieval.
        
        Args:
            clean_text: Clean extracted text
            headings: List of headings with level and text
            url: Source URL
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        # If text is short enough, return as single chunk
        if len(clean_text) <= self.max_chunk_chars:
            return [{
                "chunk_index": 0,
                "section_heading": headings[0]["text"] if headings else "",
                "chunk_text": clean_text,
                "url": url,
                "chunk_tokens": len(clean_text) // 4  # Rough estimate
            }]
        
        # Try to chunk by H2 sections
        h2_sections = self._split_by_headings(clean_text, headings)
        
        if h2_sections:
            for i, section in enumerate(h2_sections):
                heading = section.get("heading", "")
                text = section.get("text", "")
                
                # If section is still too large, split by paragraphs
                if len(text) > self.max_chunk_chars:
                    sub_chunks = self._split_by_size(text, self.max_chunk_chars)
                    for j, sub_text in enumerate(sub_chunks):
                        chunks.append({
                            "chunk_index": len(chunks),
                            "section_heading": f"{heading} (part {j+1})" if heading else "",
                            "chunk_text": sub_text,
                            "url": url,
                            "chunk_tokens": len(sub_text) // 4
                        })
                else:
                    chunks.append({
                        "chunk_index": len(chunks),
                        "section_heading": heading,
                        "chunk_text": text,
                        "url": url,
                        "chunk_tokens": len(text) // 4
                    })
        else:
            # No clear structure, just split by size
            sub_chunks = self._split_by_size(clean_text, self.max_chunk_chars)
            for i, text in enumerate(sub_chunks):
                chunks.append({
                    "chunk_index": i,
                    "section_heading": "",
                    "chunk_text": text,
                    "url": url,
                    "chunk_tokens": len(text) // 4
                })
        
        return chunks
    
    def _split_by_headings(
        self,
        text: str,
        headings: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Split text by H2 headings."""
        if not headings:
            return []
        
        # Find H2 headings in text
        sections = []
        h2_headings = [h for h in headings if h["level"] == "h2"]
        
        if not h2_headings:
            return []
        
        for i, heading in enumerate(h2_headings):
            heading_text = heading["text"]
            
            # Find heading position in text
            pattern = re.escape(heading_text)
            match = re.search(pattern, text, re.IGNORECASE)
            
            if match:
                start = match.end()
                
                # Find next H2 heading or end of text
                if i < len(h2_headings) - 1:
                    next_heading = h2_headings[i + 1]["text"]
                    next_pattern = re.escape(next_heading)
                    next_match = re.search(next_pattern, text[start:], re.IGNORECASE)
                    end = start + next_match.start() if next_match else len(text)
                else:
                    end = len(text)
                
                section_text = text[start:end].strip()
                if section_text:
                    sections.append({
                        "heading": heading_text,
                        "text": section_text
                    })
        
        return sections
    
    def _split_by_size(self, text: str, max_chars: int) -> List[str]:
        """Split text into chunks by size, trying to break at sentence boundaries."""
        chunks = []
        current_chunk = ""
        
        # Split by paragraphs first
        paragraphs = text.split("\n\n")
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # If adding this paragraph exceeds max size
            if len(current_chunk) + len(para) > max_chars and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
        
        # Add remaining chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks


def extract_and_chunk_page(
    html: str,
    url: str,
    max_chunk_tokens: int = 1000
) -> Dict[str, Any]:
    """
    Convenience function to extract and chunk a page.
    
    Args:
        html: Raw HTML
        url: Page URL
        max_chunk_tokens: Maximum tokens per chunk
        
    Returns:
        Dictionary with clean_text, headings, page_type, and chunks
    """
    extractor = ContentExtractor(max_chunk_tokens=max_chunk_tokens)
    
    # Extract clean content
    extracted = extractor.extract_clean_text(html, url)
    
    # Chunk content
    chunks = extractor.chunk_content(
        clean_text=extracted["clean_text"],
        headings=extracted["headings"],
        url=url
    )
    
    return {
        **extracted,
        "chunks": chunks
    }
