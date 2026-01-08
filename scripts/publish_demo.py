"""CLI demo script for publishing a blog post."""
import os
import sys
import time
import argparse
import requests
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_BASE = os.getenv("API_BASE", "http://localhost:8000")


def connect_site(wp_base_url: str, wp_username: str, wp_app_password: str) -> Optional[str]:
    """Connect to WordPress site and return siteId."""
    print(f"Connecting to WordPress site: {wp_base_url}")
    
    response = requests.post(
        f"{API_BASE}/api/sites/connect",
        json={
            "wpBaseUrl": wp_base_url,
            "wpUsername": wp_username,
            "wpApplicationPassword": wp_app_password
        }
    )
    
    if response.status_code != 200:
        print(f"Error connecting: {response.status_code} - {response.text}")
        return None
    
    data = response.json()
    site_id = data.get("siteId")
    print(f"✓ Connected! Site ID: {site_id}")
    print(f"  WordPress User: {data.get('wpUser', {}).get('name')}")
    return site_id


def generate_post(
    site_id: str,
    topic: str,
    focus_keyword: str,
    brand_name: str
) -> Optional[dict]:
    """Generate blog post content."""
    print(f"\nGenerating blog post about: {topic}")
    
    request_data = {
        "siteId": site_id,
        "topic": topic,
        "audience": {
            "market": "general",
            "level": "intermediate",
            "painPoints": [],
            "objections": []
        },
        "toneOfVoice": {
            "style": ["nuchter", "direct"],
            "formality": "je",
            "do": ["korte zinnen"],
            "dont": ["geen hype"]
        },
        "seo": {
            "focusKeyword": focus_keyword,
            "secondaryKeywords": [],
            "internalLinkTargets": [],
            "metaTitlePattern": f"{{topic}} | {brand_name}",
            "metaDescMaxLen": 155
        },
        "brand": {
            "name": brand_name,
            "cta": ""
        },
        "language": "nl",
        "status": "draft",
        "multilang": {
            "enabled": False,
            "languages": [],
            "strategy": "translate"
        }
    }
    
    response = requests.post(
        f"{API_BASE}/api/posts/generate",
        json=request_data
    )
    
    if response.status_code != 200:
        print(f"Error generating: {response.status_code} - {response.text}")
        return None
    
    data = response.json()
    print("✓ Post generated!")
    if "draft" in data:
        print(f"  Title: {data['draft'].get('title')}")
        print(f"  Slug: {data['draft'].get('slug')}")
    elif "drafts" in data:
        print(f"  Generated {len(data['drafts'])} language versions")
    
    return data


def publish_post(site_id: str, draft_data: dict) -> Optional[str]:
    """Publish blog post and return jobId."""
    print("\nPublishing post...")
    
    request_data = {
        "siteId": site_id
    }
    
    if "draft" in draft_data:
        request_data["draft"] = draft_data["draft"]
    elif "drafts" in draft_data:
        request_data["drafts"] = draft_data["drafts"]
    
    response = requests.post(
        f"{API_BASE}/api/posts/publish",
        json=request_data
    )
    
    if response.status_code != 200:
        print(f"Error publishing: {response.status_code} - {response.text}")
        return None
    
    data = response.json()
    job_id = data.get("jobId")
    print(f"✓ Publish job created! Job ID: {job_id}")
    return job_id


def poll_job(job_id: str, max_wait: int = 120) -> Optional[dict]:
    """Poll job status until terminal state."""
    print(f"\nPolling job {job_id}...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = requests.get(f"{API_BASE}/api/jobs/{job_id}")
        
        if response.status_code != 200:
            print(f"Error getting job: {response.status_code} - {response.text}")
            return None
        
        job = response.json()
        status = job.get("status")
        
        print(f"  Status: {status}")
        
        if status in ["success", "partial_success", "failed"]:
            print(f"\n✓ Job completed with status: {status}")
            
            if job.get("result"):
                result = job["result"]
                if result.get("wpPostIds"):
                    print("\nPublished WordPress Posts:")
                    for lang, post_id in result["wpPostIds"].items():
                        print(f"  {lang}: Post ID {post_id}")
                
                if result.get("errors"):
                    print("\nErrors:")
                    for error in result["errors"]:
                        print(f"  - {error}")
            
            if job.get("error"):
                print(f"\nError: {job.get('error')}")
            
            return job
        
        time.sleep(2)
    
    print(f"\nTimeout after {max_wait} seconds")
    return None


def main():
    parser = argparse.ArgumentParser(description="Publish a blog post to WordPress")
    parser.add_argument("--wpBaseUrl", required=True, help="WordPress base URL")
    parser.add_argument("--wpUsername", required=True, help="WordPress username")
    parser.add_argument("--wpAppPassword", required=True, help="WordPress application password")
    parser.add_argument("--topic", required=True, help="Blog post topic")
    parser.add_argument("--focusKeyword", required=True, help="SEO focus keyword")
    parser.add_argument("--brandName", default="My Brand", help="Brand name")
    
    args = parser.parse_args()
    
    # Step 1: Connect
    site_id = connect_site(args.wpBaseUrl, args.wpUsername, args.wpAppPassword)
    if not site_id:
        sys.exit(1)
    
    # Step 2: Generate
    draft_data = generate_post(site_id, args.topic, args.focusKeyword, args.brandName)
    if not draft_data:
        sys.exit(1)
    
    # Step 3: Publish
    job_id = publish_post(site_id, draft_data)
    if not job_id:
        sys.exit(1)
    
    # Step 4: Poll
    job_result = poll_job(job_id)
    if not job_result:
        sys.exit(1)
    
    print("\n✓ Demo completed!")


if __name__ == "__main__":
    main()
