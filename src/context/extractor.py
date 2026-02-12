"""Content extraction and chunking from HTML."""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import trafilatura
import requests
from urllib.parse import urljoin, urlparse
from collections import Counter

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
                logger.warning(
                    f"HTML is suspiciously small ({len(html)} bytes)")

            # Use trafilatura for main content extraction
            clean_text = trafilatura.extract(
                html,
                include_links=False,
                include_images=False,
                include_tables=True,      # Include tables (changed from False)
                no_fallback=False,
                favor_precision=False,     # Favor recall over precision
                favor_recall=True,         # Get more content, even if less precise
                deduplicate=True
            )

            # Parse HTML for headings structure
            soup = BeautifulSoup(html, "html.parser")
            headings = self._extract_headings(soup)

            # Fallback: if trafilatura fails, use BeautifulSoup
            if not clean_text:
                logger.warning(
                    f"Trafilatura failed for {url}, using BeautifulSoup fallback")
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
        logger.info(
            f"HTML structure - title: {soup.title.string if soup.title else 'None'}")
        logger.info(
            f"HTML structure - body length: {len(soup.body.get_text()) if soup.body else 0}")

        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe']):
            element.decompose()

        # Try common content containers (WordPress and general)
        content_selectors = [
            'main',
            'article',
            '[role="main"]',
            '.entry-content',      # WordPress standard
            '.post-content',       # WordPress standard
            '.content',
            '.main-content',
            '#content',
            '#main',
            '.site-content',       # WordPress common
            '.page-content',       # WordPress common
            '.elementor',          # Elementor builder
            '.wp-block-post-content',  # Gutenberg
            'body'                 # Last resort
        ]

        content_text = ""
        for selector in content_selectors:
            container = soup.select_one(selector)
            if container:
                # Get all text, preserving paragraph structure
                paragraphs = []
                for p in container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'div', 'span']):
                    text = p.get_text(strip=True)
                    # Be less strict - accept shorter text (lowered from 10 to 5)
                    if text and len(text) > 5 and not self._is_likely_noise(text):
                        paragraphs.append(text)

                content_text = "\n\n".join(paragraphs)
                logger.info(
                    f"Selector '{selector}' found {len(paragraphs)} text blocks, {len(content_text)} chars")
                if len(content_text) > 50:  # Lowered threshold from 100 to 50
                    break

        # If still no content, try body directly with more lenient filtering
        if not content_text or len(content_text) < 50:
            logger.info("Trying body fallback with lenient filtering")
            body = soup.find('body')
            if body:
                # Get visible text
                text = body.get_text(separator='\n', strip=True)
                # Clean up multiple newlines
                lines = [line.strip()
                         for line in text.split('\n') if line.strip()]
                # Filter out very short lines but be more lenient (lowered from 15 to 10)
                content_lines = [line for line in lines if len(
                    line) > 10 and not self._is_likely_noise(line)]
                content_text = "\n\n".join(content_lines)
                logger.info(
                    f"Body extraction found {len(content_lines)} lines, {len(content_text)} chars")

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
        # e.g., https://example.com or https://example.com/nl
        if parsed_path.count("/") <= 3:
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
                    sub_chunks = self._split_by_size(
                        text, self.max_chunk_chars)
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
                    next_match = re.search(
                        next_pattern, text[start:], re.IGNORECASE)
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


def extract_colors_from_html(html: str, base_url: str = None) -> List[str]:
    """
    Extract brand color hex codes from HTML, including external CSS files.
    Filters out neutrals, grays, and boring colors to focus on brand colors.
    Uses specificity scoring to prioritize colors from brand-related elements.
    Only extracts colors from CSS classes/IDs that are actually used in the HTML.

    Args:
        html: Raw HTML content
        base_url: Base URL for resolving relative CSS paths (optional)

    Returns:
        List of unique hex color codes, sorted by vibrancy and prominence
    """
    # Store colors with their specificity scores
    color_scores = {}  # {color: score}

    # Parse HTML
    soup = BeautifulSoup(html, 'html.parser')

    # Pattern for hex colors
    hex_pattern = re.compile(r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b')

    # Collect all classes and IDs actually used in the HTML (only from visible elements)
    used_classes = set()
    used_ids = set()
    hidden_classes = set()  # Track classes of hidden elements
    hidden_ids = set()  # Track IDs of hidden elements

    for tag in soup.find_all(True):  # All tags
        classes = tag.get('class', [])
        tag_id = tag.get('id')

        # Check if element is hidden
        style = tag.get('style', '')
        is_hidden = False
        if style:
            style_lower = style.lower().replace(' ', '')
            if 'display:none' in style_lower or 'visibility:hidden' in style_lower:
                is_hidden = True

        if is_hidden:
            # Track hidden elements separately
            hidden_classes.update(classes)
            if tag_id:
                hidden_ids.add(tag_id)
        else:
            # Only add visible elements
            used_classes.update(classes)
            if tag_id:
                used_ids.add(tag_id)

    logger.info(
        f"Found {len(used_classes)} visible classes and {len(used_ids)} visible IDs in HTML")
    logger.info(
        f"Found {len(hidden_classes)} hidden classes that will be ignored")

    def add_color_with_score(color: str, score: float):
        """Add or update color with specificity score."""
        if color in color_scores:
            color_scores[color] += score
        else:
            color_scores[color] = score

    def is_selector_used(css_line: str) -> bool:
        """Check if a CSS selector is actually used in the HTML."""
        # Extract class names from CSS selector (e.g., ".btn-primary" or "button.btn-primary")
        class_matches = re.findall(r'\.([a-zA-Z0-9_-]+)', css_line)
        for cls in class_matches:
            if cls in used_classes:
                return True

        # Extract ID from CSS selector (e.g., "#header")
        id_matches = re.findall(r'#([a-zA-Z0-9_-]+)(?:\s|{|:|,|$)', css_line)
        for id_name in id_matches:
            if id_name in used_ids:
                return True

        # Check for element selectors (header, nav, button, etc.)
        element_tags = ['header', 'nav', 'footer', 'button', 'a', 'body',
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'section', 'article']
        for tag in element_tags:
            # Match tag at start or after space/comma (e.g., "header {" or "div, header")
            if re.search(rf'\b{tag}\b', css_line):
                return True

        return False

    def is_element_visible(tag) -> bool:
        """Check if an HTML element is visible (not hidden via style)."""
        style = tag.get('style', '')
        if style:
            style_lower = style.lower()
            if 'display:none' in style_lower.replace(' ', '') or 'display: none' in style_lower:
                return False
            if 'visibility:hidden' in style_lower.replace(' ', '') or 'visibility: hidden' in style_lower:
                return False
        return True

    def should_skip_css_line(selector_line: str, property_line: str) -> Tuple[bool, float]:
        """Check if CSS should be skipped or penalized. Returns (skip, penalty_multiplier)."""
        selector_lower = selector_line.lower()
        property_lower = property_line.lower()

        # Skip hover, focus, active, visited states (not default visible colors)
        if any(state in selector_lower for state in [':hover', ':focus', ':active', ':visited', ':checked']):
            return True, 0.0

        # Skip media queries for non-desktop (we want desktop brand colors)
        # Note: This is a simplified check, full media query parsing would be more complex

        # Heavily penalize display:none and visibility:hidden
        if 'display' in property_lower and 'none' in property_lower:
            return True, 0.0
        if 'visibility' in property_lower and 'hidden' in property_lower:
            return True, 0.0

        return False, 1.0

    # Extract from inline styles with element-based scoring
    for tag in soup.find_all(style=True):
        # Skip hidden elements
        if not is_element_visible(tag):
            continue

        style = tag.get('style', '')
        matches = hex_pattern.findall(style)

        # Calculate specificity based on element type and classes
        score = 1.0
        tag_name = tag.name.lower()
        classes = tag.get('class', [])

        # Higher score for prominent elements
        if tag_name in ['header', 'nav', 'button', 'a']:
            score *= 3.0
        if tag_name in ['h1', 'h2', 'h3']:
            score *= 2.5

        # Higher score for brand-related classes
        for cls in classes:
            cls_lower = cls.lower()
            if any(brand_word in cls_lower for brand_word in ['brand', 'primary', 'accent', 'hero', 'cta', 'btn']):
                score *= 4.0
                break
            # Penalize social media classes
            if any(social in cls_lower for social in ['facebook', 'twitter', 'instagram', 'linkedin', 'social', 'share']):
                score *= 0.1
                break

        for match in matches:
            add_color_with_score(match, score)

    # Extract from style tags
    for style_tag in soup.find_all('style'):
        if style_tag.string:
            css_content = style_tag.string

            # Parse CSS line by line to check if selectors are used
            lines = css_content.split('\n')
            for i, line in enumerate(lines):
                matches = hex_pattern.findall(line)
                if not matches:
                    continue

                # Find the selector for this line by looking backwards
                selector_line = ""
                for j in range(i, max(0, i-10), -1):  # Look back up to 10 lines
                    if '{' in lines[j]:
                        # Found the selector line
                        selector_line = lines[j].split('{')[0]
                        break

                # Only process colors if the selector is actually used in HTML
                if selector_line and is_selector_used(selector_line):
                    # Check if this CSS should be skipped (hover states, hidden elements)
                    skip, penalty = should_skip_css_line(selector_line, line)
                    if skip:
                        continue

                    for match in matches:
                        score = 2.0  # Base score for internal CSS

                        line_lower = line.lower()
                        selector_lower = selector_line.lower()

                        # Boost brand-related selectors
                        if any(brand_word in selector_lower or brand_word in line_lower
                               for brand_word in ['brand', 'primary', 'accent', 'hero', 'cta', 'btn', 'header', 'nav']):
                            score *= 3.0

                        # Heavily penalize social media selectors
                        if any(social in selector_lower or social in line_lower
                               for social in ['facebook', 'twitter', 'instagram', 'linkedin', 'social', 'share', 'youtube', 'pinterest']):
                            score *= 0.05

                        # Penalize utility/border/shadow colors
                        if any(util in line_lower for util in ['border', 'shadow', 'outline', 'divider']):
                            score *= 0.3

                        add_color_with_score(match, score)

    # Fetch and parse external CSS files
    if base_url:
        for link_tag in soup.find_all('link', rel='stylesheet'):
            href = link_tag.get('href')
            if href:
                try:
                    # Resolve relative URL
                    css_url = urljoin(base_url, href)

                    # Only fetch CSS from same domain (security)
                    if urlparse(css_url).netloc == urlparse(base_url).netloc or not urlparse(css_url).netloc:
                        logger.info(f"Fetching external CSS: {css_url}")
                        response = requests.get(css_url, timeout=5)

                        if response.status_code == 200:
                            css_content = response.text

                            # Parse CSS line by line to check if selectors are used
                            lines = css_content.split('\n')
                            for i, line in enumerate(lines):
                                matches = hex_pattern.findall(line)
                                if not matches:
                                    continue

                                # Find the selector for this line by looking backwards
                                selector_line = ""
                                # Look back up to 10 lines
                                for j in range(i, max(0, i-10), -1):
                                    if '{' in lines[j]:
                                        # Found the selector line
                                        selector_line = lines[j].split('{')[0]
                                        break

                                # Only process colors if the selector is actually used in HTML
                                if selector_line and is_selector_used(selector_line):
                                    # Check if this CSS should be skipped (hover states, hidden elements)
                                    skip, penalty = should_skip_css_line(
                                        selector_line, line)
                                    if skip:
                                        continue

                                    for match in matches:
                                        score = 5.0  # High base score for external CSS

                                        line_lower = line.lower()
                                        selector_lower = selector_line.lower()

                                        # Boost brand-related selectors
                                        if any(brand_word in selector_lower or brand_word in line_lower
                                               for brand_word in ['brand', 'primary', 'accent', 'hero', 'cta', 'btn', 'header', 'nav', 'logo']):
                                            score *= 3.0

                                        # Heavily penalize social media selectors
                                        if any(social in selector_lower or social in line_lower
                                               for social in ['facebook', 'twitter', 'instagram', 'linkedin', 'social', 'share', 'youtube', 'pinterest']):
                                            score *= 0.05

                                        # Penalize utility colors
                                        if any(util in line_lower for util in
                                               ['border', 'shadow', 'outline', 'divider', 'gray', 'grey']):
                                            score *= 0.2

                                        add_color_with_score(match, score)

                except Exception as e:
                    logger.warning(f"Failed to fetch CSS from {css_url}: {e}")
                    continue

    # Convert 3-char hex to 6-char hex and normalize
    normalized_colors = {}
    for color, score in color_scores.items():
        if len(color) == 3:
            # Expand #abc to #aabbcc
            color = ''.join([c*2 for c in color])
        hex_color = f"#{color.upper()}"

        # Accumulate scores for the same normalized color
        if hex_color in normalized_colors:
            normalized_colors[hex_color] += score
        else:
            normalized_colors[hex_color] = score

    # Filter out boring colors (more lenient thresholds)
    def is_brand_color(hex_color: str) -> bool:
        """Check if color is interesting enough to be a brand color."""
        # Remove # for processing
        hex_val = hex_color.lstrip('#')

        # Convert to RGB
        r = int(hex_val[0:2], 16)
        g = int(hex_val[2:4], 16)
        b = int(hex_val[4:6], 16)

        # Filter out known social media brand colors (not site brand colors)
        social_media_colors = {
            '#3B5998', '#3B5999',  # Facebook blue
            '#1DA1F2', '#1DA1F3',  # Twitter blue
            '#E4405F', '#E4405E',  # Instagram gradient pink
            '#0077B5', '#0077B6',  # LinkedIn blue
            '#FF0000', '#FF0001',  # YouTube red
            '#25D366', '#25D367',  # WhatsApp green
            '#EA4335', '#EA4336',  # Google red
            '#4285F4', '#4285F5',  # Google blue
            '#FBBC05', '#FBBC04',  # Google yellow
            '#34A853', '#34A854',  # Google green
            '#E60023', '#E60024',  # Pinterest red
            '#BD081C', '#BD081D',  # Pinterest dark red
            '#00AFF0', '#00AFF1',  # Skype/generic social blue
            '#0088CC', '#0088CD',  # Telegram blue
            '#25D366', '#25D365',  # WhatsApp green
        }

        if hex_color.upper() in social_media_colors:
            logger.info(f"Filtering out social media color: {hex_color}")
            return False

        # Filter 1: Too dark (almost black) - more lenient for dark brand colors
        if max(r, g, b) < 20:  # Lowered from 30 to allow navy/dark colors
            return False

        # Filter 2: Too light (almost white)
        if min(r, g, b) > 240:
            return False

        # Filter 3: Gray/neutral (low saturation) - more lenient for muted brands
        # Check if R, G, B are too similar
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        saturation = (max_val - min_val) / \
            (max_val + 1)  # Avoid division by zero

        if saturation < 0.10:  # Lowered from 0.15 to allow muted brand colors
            return False

        return True

    # Calculate color "vibrancy" for sorting
    def color_vibrancy(hex_color: str) -> float:
        """Calculate how vibrant/saturated a color is (higher = more brand-like)."""
        hex_val = hex_color.lstrip('#')
        r = int(hex_val[0:2], 16)
        g = int(hex_val[2:4], 16)
        b = int(hex_val[4:6], 16)

        max_val = max(r, g, b)
        min_val = min(r, g, b)

        # Saturation
        saturation = (max_val - min_val) / (max_val + 1)

        # Brightness (prefer medium brightness over very dark/light)
        brightness = (r + g + b) / 3
        # Peak at mid-brightness
        brightness_score = 1.0 - abs(brightness - 128) / 128

        return saturation * 2 + brightness_score  # Weight saturation higher

    # Cluster similar colors
    def cluster_similar_colors(colors_with_scores: Dict[str, float]) -> Dict[str, float]:
        """Cluster similar colors and combine their scores."""
        clustered = {}
        processed = set()

        for color1, score1 in colors_with_scores.items():
            if color1 in processed:
                continue

            # This color becomes the representative of its cluster
            cluster_score = score1
            processed.add(color1)

            # Find similar colors and merge them
            hex_val1 = color1.lstrip('#')
            r1 = int(hex_val1[0:2], 16)
            g1 = int(hex_val1[2:4], 16)
            b1 = int(hex_val1[4:6], 16)

            for color2, score2 in colors_with_scores.items():
                if color2 in processed or color2 == color1:
                    continue

                # Calculate color distance
                hex_val2 = color2.lstrip('#')
                r2 = int(hex_val2[0:2], 16)
                g2 = int(hex_val2[2:4], 16)
                b2 = int(hex_val2[4:6], 16)

                # Euclidean distance in RGB space
                distance = ((r1 - r2) ** 2 + (g1 - g2)
                            ** 2 + (b1 - b2) ** 2) ** 0.5

                # If colors are very similar (distance < 80), merge them
                # Higher threshold to better group similar shades (e.g., multiple blues, greens)
                if distance < 80:
                    cluster_score += score2
                    processed.add(color2)

            clustered[color1] = cluster_score

        return clustered

    # Cluster similar colors to avoid duplicates
    clustered_colors = cluster_similar_colors(normalized_colors)

    # Filter and sort colors by combined score (specificity + vibrancy)
    brand_colors = []
    for color, score in clustered_colors.items():
        if is_brand_color(color):
            vibrancy = color_vibrancy(color)
            # Combine specificity score with vibrancy
            combined_score = score * vibrancy
            brand_colors.append((color, combined_score))

    # Sort by combined score
    brand_colors.sort(key=lambda x: x[1], reverse=True)

    # Return top 10 colors (without scores)
    return [color for color, score in brand_colors[:10]]
