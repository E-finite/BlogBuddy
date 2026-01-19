"""Test script voor website context systeem."""
import requests
import json
import time

# API base URL
BASE_URL = "http://localhost:5000"

def test_connect_site():
    """Test 1: Connect een WordPress site."""
    print("\n" + "="*80)
    print("TEST 1: Connect WordPress Site")
    print("="*80)
    
    # Vervang met je eigen gegevens
    payload = {
        "wpBaseUrl": "https://jouwsite.nl",  # <-- Vervang dit
        "wpUsername": "admin",                # <-- Vervang dit
        "wpApplicationPassword": "xxxx xxxx xxxx xxxx"  # <-- Vervang dit
    }
    
    print(f"\n📡 Connecting to {payload['wpBaseUrl']}...")
    
    response = requests.post(
        f"{BASE_URL}/api/sites/connect",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        site_id = data.get("siteId")
        print(f"✅ Site connected!")
        print(f"   Site ID: {site_id}")
        print(f"   User: {data.get('wpUser', {}).get('name')}")
        return site_id
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return None


def test_crawl_site(site_id):
    """Test 2: Crawl de website."""
    print("\n" + "="*80)
    print("TEST 2: Crawl Website")
    print("="*80)
    
    payload = {
        "maxDepth": 2,
        "maxPages": 10  # Klein voor snelle test
    }
    
    print(f"\n🕷️  Starting crawl for site {site_id}...")
    print(f"   Max depth: {payload['maxDepth']}")
    print(f"   Max pages: {payload['maxPages']}")
    print("\n⏳ This may take 10-30 seconds...")
    
    response = requests.post(
        f"{BASE_URL}/api/sites/{site_id}/crawl",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Crawl completed!")
        print(f"   Pages crawled: {data.get('pages_crawled')}")
        print(f"   Pages stored: {data.get('pages_stored')}")
        print(f"   Chunks created: {data.get('chunks_stored')}")
        print(f"   Site DNA generated: {data.get('site_dna_generated')}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False


def test_get_site_dna(site_id):
    """Test 3: Bekijk Site DNA."""
    print("\n" + "="*80)
    print("TEST 3: Get Site DNA")
    print("="*80)
    
    response = requests.get(f"{BASE_URL}/api/sites/{site_id}/site-dna")
    
    if response.status_code == 200:
        dna = response.json()
        print(f"\n✅ Site DNA retrieved!")
        print(f"\n📊 Brand Summary:")
        print(f"   {dna.get('brand_summary', 'N/A')}")
        print(f"\n🎯 Target Audiences:")
        for audience in dna.get('target_audiences', []):
            print(f"   - {audience}")
        print(f"\n💡 Tone Keywords:")
        print(f"   {', '.join(dna.get('tone_keywords', []))}")
        print(f"\n🚫 Avoid Words:")
        print(f"   {', '.join(dna.get('avoid_words', []))}")
        print(f"\n✓ Proof Points (top 3):")
        for point in dna.get('proof_points', [])[:3]:
            print(f"   - {point}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False


def test_ingest_stats(site_id):
    """Test 4: Bekijk ingest statistieken."""
    print("\n" + "="*80)
    print("TEST 4: Get Ingest Stats")
    print("="*80)
    
    response = requests.get(f"{BASE_URL}/api/sites/{site_id}/ingest-stats")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"\n✅ Stats retrieved!")
        print(f"   Pages: {stats.get('pages_count')}")
        print(f"   Chunks: {stats.get('chunks_count')}")
        print(f"   Last crawl: {stats.get('last_crawl')}")
        print(f"   DNA generated: {stats.get('site_dna_generated_at')}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False


def test_generate_post_with_context(site_id):
    """Test 5: Genereer blog MET website context."""
    print("\n" + "="*80)
    print("TEST 5: Generate Blog Post WITH Website Context")
    print("="*80)
    
    payload = {
        "siteId": site_id,
        "topic": "Hoe kies je de juiste projectmanagement software",
        "audience": {
            "market": "B2B",
            "level": "intermediate",
            "painPoints": [
                "Te veel tijd kwijt aan planning",
                "Geen overzicht over projecten"
            ],
            "objections": []
        },
        "toneOfVoice": {
            "style": ["nuchter", "praktisch", "deskundig"],
            "formality": "je",
            "do": ["gebruik voorbeelden", "wees concreet"],
            "dont": ["overdrijf niet", "geen jargon"]
        },
        "seo": {
            "focusKeyword": "projectmanagement software",
            "secondaryKeywords": ["projecttool", "planning software"],
            "internalLinkTargets": []
        },
        "brand": {
            "name": "JouwBedrijf",
            "cta": "Bekijk onze oplossing"
        },
        "status": "draft",
        "generateImage": False  # Sneller voor test
    }
    
    print(f"\n📝 Generating blog post...")
    print(f"   Topic: {payload['topic']}")
    print(f"   Focus keyword: {payload['seo']['focusKeyword']}")
    print(f"\n⏳ This may take 30-60 seconds (GPT processing)...")
    
    response = requests.post(
        f"{BASE_URL}/api/posts/generate",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        data = response.json()
        draft = data.get('draft', {})
        print(f"\n✅ Blog post generated WITH website context!")
        print(f"\n📄 Title: {draft.get('title')}")
        print(f"   Slug: {draft.get('slug')}")
        print(f"   Excerpt: {draft.get('excerpt', '')[:100]}...")
        print(f"\n🔍 SEO:")
        yoast = draft.get('yoast', {})
        print(f"   Focus KW: {yoast.get('focuskw')}")
        print(f"   Meta title: {yoast.get('seo_title')}")
        print(f"   Meta desc: {yoast.get('meta_desc', '')[:80]}...")
        print(f"\n📊 Content length: {len(draft.get('contentHtml', ''))} chars")
        
        # Check for internal links
        content = draft.get('contentHtml', '')
        link_count = content.count('<a href=')
        print(f"   Internal links: {link_count}")
        
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False


def test_generate_post_without_context():
    """Test 6: Genereer blog ZONDER website context (ter vergelijking)."""
    print("\n" + "="*80)
    print("TEST 6: Generate Blog Post WITHOUT Website Context (comparison)")
    print("="*80)
    
    payload = {
        "siteId": "dummy-site-id",  # Niet-bestaande site
        "topic": "Hoe kies je de juiste projectmanagement software",
        "audience": {
            "market": "B2B",
            "level": "intermediate",
            "painPoints": [
                "Te veel tijd kwijt aan planning",
                "Geen overzicht over projecten"
            ],
            "objections": []
        },
        "toneOfVoice": {
            "style": ["nuchter", "praktisch", "deskundig"],
            "formality": "je",
            "do": ["gebruik voorbeelden", "wees concreet"],
            "dont": ["overdrijf niet", "geen jargon"]
        },
        "seo": {
            "focusKeyword": "projectmanagement software",
            "secondaryKeywords": ["projecttool", "planning software"],
            "internalLinkTargets": []
        },
        "brand": {
            "name": "JouwBedrijf",
            "cta": "Bekijk onze oplossing"
        },
        "status": "draft",
        "generateImage": False
    }
    
    print(f"\n📝 Generating blog post WITHOUT context...")
    print(f"   (Using non-existent site_id so no context will be loaded)")
    
    # Note: Dit zal falen omdat site niet bestaat
    # In productie zou je gewoon site_id weglaten voor generic content
    print(f"\n⚠️  Skipping - would need to adjust code to allow missing site_id")


def run_all_tests():
    """Run alle tests."""
    print("\n" + "="*80)
    print("🚀 WEBSITE CONTEXT SYSTEM - INTEGRATION TEST")
    print("="*80)
    print("\nDeze test suite test het complete website context systeem:")
    print("1. Connect WordPress site")
    print("2. Crawl website en genereer Site DNA")
    print("3. Bekijk Site DNA")
    print("4. Bekijk statistieken")
    print("5. Genereer blog MET website context")
    
    print("\n⚠️  BELANGRIJK: Start eerst de Flask app:")
    print("   python app.py")
    print("\n⚠️  Vervang in dit script je WordPress credentials!")
    
    input("\nDruk op Enter om te starten...")
    
    # Test 1: Connect site
    site_id = test_connect_site()
    if not site_id:
        print("\n❌ Test failed. Fix credentials and try again.")
        return
    
    time.sleep(1)
    
    # Test 2: Crawl site
    success = test_crawl_site(site_id)
    if not success:
        print("\n❌ Test failed.")
        return
    
    time.sleep(1)
    
    # Test 3: Get Site DNA
    success = test_get_site_dna(site_id)
    if not success:
        print("\n❌ Test failed.")
        return
    
    time.sleep(1)
    
    # Test 4: Get stats
    success = test_ingest_stats(site_id)
    if not success:
        print("\n❌ Test failed.")
        return
    
    time.sleep(1)
    
    # Test 5: Generate with context
    success = test_generate_post_with_context(site_id)
    if not success:
        print("\n❌ Test failed.")
        return
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED!")
    print("="*80)
    print(f"\n💾 Site ID: {site_id}")
    print("\nJe kunt nu:")
    print(f"1. Meer blogs genereren met dit site_id")
    print(f"2. De Site DNA bekijken: GET /api/sites/{site_id}/site-dna")
    print(f"3. Opnieuw crawlen: POST /api/sites/{site_id}/crawl")


if __name__ == "__main__":
    run_all_tests()
