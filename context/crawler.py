"""Website crawler with robots.txt respect and throttling."""
import logging
import time
import hashlib
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebsiteCrawler:
    """Crawls website pages respecting robots.txt and throttling."""
    
    def __init__(
        self,
        base_url: str,
        max_depth: int = 3,
        max_pages: int = 50,
        delay: float = 1.0,
        timeout: float = 10.0,
        user_agent: str = "BlogGenerator/1.0"
    ):
        """
        Initialize crawler.
        
        Args:
            base_url: Root URL to start crawling from
            max_depth: Maximum depth to crawl (0 = only seed URLs)
            max_pages: Maximum number of pages to crawl
            delay: Delay between requests in seconds
            timeout: Request timeout in seconds
            user_agent: User agent string
        """
        self.base_url = base_url.rstrip("/")
        self.domain = urlparse(base_url).netloc
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.delay = delay
        self.timeout = timeout
        self.user_agent = user_agent
        
        self.visited: Set[str] = set()
        self.to_visit: List[tuple] = []  # (url, depth)
        self.results: List[Dict[str, Any]] = []
        self.robots_parser: Optional[RobotFileParser] = None
        self.last_request_time = 0.0
        
        # URL patterns to exclude
        self.exclude_patterns = [
            "/wp-admin", "/wp-login", "/cart", "/checkout", 
            "/account", "/my-account", "/wp-content/uploads",
            "/feed", "/comments", "/trackback"
        ]
        
        # Query parameters to strip
        self.strip_params = ["utm_", "fbclid", "gclid", "ref", "source"]
    
    def _init_robots_parser(self) -> None:
        """Initialize robots.txt parser."""
        try:
            self.robots_parser = RobotFileParser()
            robots_url = urljoin(self.base_url, "/robots.txt")
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()
            logger.info(f"Loaded robots.txt from {robots_url}")
        except Exception as e:
            logger.warning(f"Could not load robots.txt: {e}")
            self.robots_parser = None
    
    def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        if self.robots_parser is None:
            return True
        try:
            return self.robots_parser.can_fetch(self.user_agent, url)
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {e}")
            return True
    
    def _normalize_url(self, url: str) -> Optional[str]:
        """Normalize URL and return None if should be excluded."""
        # Remove fragment
        url, _ = urldefrag(url)
        
        # Parse URL
        parsed = urlparse(url)
        
        # Must be same domain
        if parsed.netloc and parsed.netloc != self.domain:
            return None
        
        # Must be http/https
        if parsed.scheme and parsed.scheme not in ["http", "https"]:
            return None
        
        # Check exclude patterns
        for pattern in self.exclude_patterns:
            if pattern in parsed.path:
                return None
        
        # Strip tracking parameters
        query_parts = []
        if parsed.query:
            for part in parsed.query.split("&"):
                key = part.split("=")[0]
                if not any(key.startswith(sp.rstrip("_")) for sp in self.strip_params):
                    query_parts.append(part)
        
        # Rebuild URL
        clean_query = "&".join(query_parts) if query_parts else ""
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if clean_query:
            normalized += f"?{clean_query}"
        
        return normalized
    
    def _throttle(self) -> None:
        """Throttle requests to respect delay."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()
    
    def _fetch_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch a single page."""
        try:
            self._throttle()
            
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "nl,en;q=0.9"
            }
            
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
            
            # Log status
            logger.info(f"Fetched {url} - Status: {response.status_code}")
            
            # Check if successful
            if response.status_code != 200:
                logger.warning(f"Skipping {url} - HTTP {response.status_code}")
                return None
            
            # Check content type
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type.lower():
                logger.debug(f"Skipping non-HTML content: {url}")
                return None
            
            # Get final URL after redirects
            final_url = str(response.url)
            
            # Parse HTML
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Get title
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            
            # Get canonical URL
            canonical_tag = soup.find("link", rel="canonical")
            canonical_url = canonical_tag.get("href") if canonical_tag else final_url
            
            # Compute content hash for deduplication
            content_hash = hashlib.md5(response.text.encode()).hexdigest()
            
            # Extract links for further crawling
            links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag.get("href")
                absolute_url = urljoin(final_url, href)
                normalized = self._normalize_url(absolute_url)
                if normalized:
                    links.append(normalized)
            
            return {
                "url": final_url,
                "canonical_url": canonical_url,
                "title": title,
                "html": response.text,
                "status_code": response.status_code,
                "content_hash": content_hash,
                "links": links,
                "fetched_at": datetime.utcnow().isoformat()
            }
        
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching {url}")
            return None
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def crawl(self, seed_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl website starting from seed URLs.
        
        Args:
            seed_urls: List of URLs to start from
            
        Returns:
            List of page data dictionaries
        """
        logger.info(f"Starting crawl of {self.base_url}")
        logger.info(f"Max depth: {self.max_depth}, Max pages: {self.max_pages}")
        
        # Initialize robots.txt parser
        self._init_robots_parser()
        
        # Add seed URLs to queue
        for url in seed_urls:
            normalized = self._normalize_url(url)
            if normalized:
                self.to_visit.append((normalized, 0))
        
        # Crawl
        while self.to_visit and len(self.results) < self.max_pages:
            url, depth = self.to_visit.pop(0)
            
            # Skip if already visited
            if url in self.visited:
                continue
            
            # Skip if too deep
            if depth > self.max_depth:
                continue
            
            # Skip if robots.txt disallows
            if not self._can_fetch(url):
                logger.debug(f"Robots.txt disallows: {url}")
                continue
            
            logger.info(f"Fetching [{len(self.results)+1}/{self.max_pages}] depth={depth}: {url}")
            
            # Fetch page
            page_data = self._fetch_page(url)
            
            # Mark as visited
            self.visited.add(url)
            
            if page_data:
                # Check for duplicates by content hash
                existing_hashes = {r.get("content_hash") for r in self.results}
                if page_data["content_hash"] not in existing_hashes:
                    self.results.append(page_data)
                    
                    # Add links to queue if not at max depth
                    if depth < self.max_depth:
                        for link in page_data["links"]:
                            if link not in self.visited:
                                self.to_visit.append((link, depth + 1))
                else:
                    logger.debug(f"Duplicate content detected: {url}")
        
        logger.info(f"Crawl complete. Fetched {len(self.results)} unique pages.")
        return self.results


def crawl_website(
    base_url: str,
    seed_urls: Optional[List[str]] = None,
    max_depth: int = 3,
    max_pages: int = 50
) -> List[Dict[str, Any]]:
    """
    Convenience function to crawl a website.
    
    Args:
        base_url: Base URL of the website
        seed_urls: Seed URLs to start from (defaults to [base_url])
        max_depth: Maximum crawl depth
        max_pages: Maximum pages to crawl
        
    Returns:
        List of page data dictionaries
    """
    if seed_urls is None:
        seed_urls = [base_url]
    
    crawler = WebsiteCrawler(
        base_url=base_url,
        max_depth=max_depth,
        max_pages=max_pages
    )
    
    return crawler.crawl(seed_urls)
