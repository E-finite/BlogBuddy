"""WordPress REST API client with retry logic."""
import requests
import time
import logging
from typing import Dict, Any, Optional, Tuple
from requests.auth import HTTPBasicAuth
import crypto_utils

logger = logging.getLogger(__name__)


def _retry_request(func, max_retries: int = 3, base_delay: float = 1.0):
    """Retry a request function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            response = func()
            if response.status_code in [429, 500, 502, 503, 504]:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Request failed with {response.status_code}, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Request error: {e}, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            raise
    return response


def test_connection(wp_base_url: str, username: str, app_password: str) -> Dict[str, Any]:
    """Test WordPress connection and return user info."""
    url = f"{wp_base_url}/wp-json/wp/v2/users/me"
    auth = HTTPBasicAuth(username, app_password)
    
    response = _retry_request(lambda: requests.get(url, auth=auth, timeout=10))
    response.raise_for_status()
    return response.json()


def create_post(site: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a WordPress post."""
    wp_base_url = site["wp_base_url"]
    username = site["wp_username"]
    app_password = crypto_utils.decrypt(site["wp_app_password_enc"])
    
    url = f"{wp_base_url}/wp-json/wp/v2/posts"
    auth = HTTPBasicAuth(username, app_password)
    
    logger.info(f"Creating WordPress post with payload keys: {list(payload.keys())}")
    
    try:
        response = _retry_request(lambda: requests.post(url, json=payload, auth=auth, timeout=30))
        
        if not response.ok:
            error_body = response.text
            logger.error(f"WordPress API error {response.status_code}: {error_body}")
            logger.error(f"Request payload was: {payload}")
            response.raise_for_status()
        
        return response.json()
    except requests.exceptions.HTTPError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating WordPress post: {e}")
        logger.error(f"Payload was: {payload}")
        raise


def update_post(site: Dict[str, Any], post_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update a WordPress post."""
    wp_base_url = site["wp_base_url"]
    username = site["wp_username"]
    app_password = crypto_utils.decrypt(site["wp_app_password_enc"])
    
    url = f"{wp_base_url}/wp-json/wp/v2/posts/{post_id}"
    auth = HTTPBasicAuth(username, app_password)
    
    response = _retry_request(lambda: requests.post(url, json=payload, auth=auth, timeout=30))
    response.raise_for_status()
    return response.json()


def upload_media(site: Dict[str, Any], filename: str, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    """Upload media to WordPress."""
    wp_base_url = site["wp_base_url"]
    username = site["wp_username"]
    app_password = crypto_utils.decrypt(site["wp_app_password_enc"])
    
    url = f"{wp_base_url}/wp-json/wp/v2/media"
    auth = HTTPBasicAuth(username, app_password)
    
    files = {
        "file": (filename, image_bytes, mime_type)
    }
    data = {
        "title": filename,
        "status": "inherit"
    }
    
    response = _retry_request(lambda: requests.post(url, files=files, data=data, auth=auth, timeout=60))
    response.raise_for_status()
    return response.json()


def set_yoast_meta(site: Dict[str, Any], post_id: int, focuskw: str, seo_title: str, meta_desc: str) -> Dict[str, Any]:
    """Set Yoast SEO meta via custom endpoint."""
    wp_base_url = site["wp_base_url"]
    username = site["wp_username"]
    app_password = crypto_utils.decrypt(site["wp_app_password_enc"])
    
    url = f"{wp_base_url}/wp-json/yoast-api/v1/update-meta"
    auth = HTTPBasicAuth(username, app_password)
    
    payload = {
        "post_id": post_id,
        "focuskw": focuskw,
        "seo_title": seo_title,
        "meta_desc": meta_desc
    }
    
    response = _retry_request(lambda: requests.post(url, json=payload, auth=auth, timeout=30))
    # If endpoint doesn't exist (plugin inactive), log warning but don't fail
    if response.status_code == 404:
        logger.warning(f"Yoast API endpoint not found (plugin may be inactive): {url}")
        return {"status": "skipped", "reason": "endpoint_not_found"}
    response.raise_for_status()
    return response.json()


def link_polylang_translations(site: Dict[str, Any], translations_map: Dict[str, int]) -> Dict[str, Any]:
    """Link Polylang translations via custom endpoint."""
    wp_base_url = site["wp_base_url"]
    username = site["wp_username"]
    app_password = crypto_utils.decrypt(site["wp_app_password_enc"])
    
    url = f"{wp_base_url}/wp-json/my-plugin/v1/link-translations"
    auth = HTTPBasicAuth(username, app_password)
    
    payload = {
        "translations": translations_map
    }
    
    response = _retry_request(lambda: requests.post(url, json=payload, auth=auth, timeout=30))
    # If endpoint doesn't exist (plugin inactive), log warning but don't fail
    if response.status_code == 404:
        logger.warning(f"Polylang API endpoint not found (plugin may be inactive): {url}")
        return {"status": "skipped", "reason": "endpoint_not_found"}
    response.raise_for_status()
    return response.json()
