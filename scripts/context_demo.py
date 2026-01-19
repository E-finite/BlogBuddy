"""Demo script for website context extraction."""
import sys
import logging
from pprint import pprint
from context.ingest import ingest_website, get_ingest_stats
from context.site_dna import get_site_dna
from context.context_retrieval import build_context_bundle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_crawl(site_id: str):
    """Demo: crawl a website."""
    print("\n" + "="*80)
    print("DEMO: Website Crawl & Ingest")
    print("="*80)
    
    # Ingest website
    print("\nStarting website ingest...")
    result = ingest_website(
        site_id=site_id,
        max_depth=2,
        max_pages=20  # Small for demo
    )
    
    print("\n✅ Ingest completed!")
    pprint(result)
    
    # Get stats
    print("\n" + "-"*80)
    print("Ingest Statistics:")
    print("-"*80)
    stats = get_ingest_stats(site_id)
    pprint(stats)
    
    # Get Site DNA
    print("\n" + "-"*80)
    print("Site DNA:")
    print("-"*80)
    dna = get_site_dna(site_id)
    if dna:
        print(f"\n📊 Brand Summary:\n{dna['brand_summary']}")
        print(f"\n🎯 Target Audiences: {', '.join(dna['target_audiences'])}")
        print(f"\n💡 Tone Keywords: {', '.join(dna['tone_keywords'])}")
        print(f"\n🚫 Avoid Words: {', '.join(dna['avoid_words'])}")
        print(f"\n✓ Proof Points:")
        for point in dna['proof_points'][:3]:
            print(f"  - {point}")
    
    print("\n✅ Demo completed!")


def demo_context_retrieval(site_id: str):
    """Demo: retrieve context for a blog topic."""
    print("\n" + "="*80)
    print("DEMO: Context Retrieval for Blog Generation")
    print("="*80)
    
    # Example blog topic
    topic = "Hoe kies je de juiste projectmanagement software"
    
    seo = {
        "focusKeyword": "projectmanagement software",
        "secondaryKeywords": ["projecttool", "planning software", "taakbeheer"]
    }
    
    audience = {
        "market": "B2B",
        "painPoints": [
            "Te veel tijd kwijt aan planning",
            "Geen overzicht over projecten",
            "Teamcommunicatie verloopt moeizaam"
        ]
    }
    
    print(f"\n📝 Topic: {topic}")
    print(f"🔑 Focus Keyword: {seo['focusKeyword']}")
    print(f"👥 Pain Points: {', '.join(audience['painPoints'][:2])}...")
    
    # Build context bundle
    print("\n🔍 Building context bundle...")
    bundle = build_context_bundle(
        site_id=site_id,
        topic=topic,
        seo=seo,
        audience=audience,
        max_snippets=6
    )
    
    print(f"\n✅ Context bundle created!")
    print(f"\n📦 Site DNA available: {bool(bundle.get('site_dna'))}")
    print(f"📄 Relevant snippets: {len(bundle.get('relevant_snippets', []))}")
    
    print("\n" + "-"*80)
    print("Top Relevant Snippets:")
    print("-"*80)
    
    for i, snippet in enumerate(bundle['relevant_snippets'][:3], 1):
        print(f"\n{i}. {snippet['heading'] or '(no heading)'}")
        print(f"   URL: {snippet['url']}")
        print(f"   Excerpt: {snippet['excerpt'][:150]}...")
    
    print("\n✅ Demo completed!")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/context_demo.py <action> <site_id>")
        print("Actions: crawl, retrieve")
        sys.exit(1)
    
    action = sys.argv[1]
    site_id = sys.argv[2]
    
    if action == "crawl":
        demo_crawl(site_id)
    elif action == "retrieve":
        demo_context_retrieval(site_id)
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
