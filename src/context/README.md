# Website Context Extraction voor Blog Generatie

Dit systeem crawlt je website, extraheert de content, en gebruikt dit om consistente, on-brand blogartikelen te genereren die geen hallucinerende claims maken.

## Architectuur

### Fase A: Website Ingest (periodiek)
1. **Crawler** - Crawlt website met robots.txt respect en throttling
2. **Extractor** - Extraheert clean text met trafilatura en chunked per sectie
3. **Site DNA** - Genereert brand identity uit kernpagina's met GPT

### Fase B: Blog Generation (per artikel)
4. **Context Retrieval** - Selecteert relevante snippets op basis van topic/keywords
5. **Blog Generator** - Gebruikt website context in prompt voor consistente content

## Database Schema

- `scraped_pages` - Gescrapete pagina's met clean text
- `page_chunks` - Chunks voor retrieval (max 1000 tokens)
- `site_dna` - Geëxtraheerde brand identity (tone, USPs, pain points)

## API Endpoints

### Crawl Website
```bash
POST /api/sites/{siteId}/crawl
{
  "seedUrls": ["https://example.com", "https://example.com/diensten"],
  "maxDepth": 3,
  "maxPages": 50
}
```

Response:
```json
{
  "site_id": "...",
  "pages_crawled": 45,
  "pages_stored": 43,
  "chunks_stored": 287,
  "site_dna_generated": true,
  "completed_at": "2026-01-19T12:00:00"
}
```

### Get Site DNA
```bash
GET /api/sites/{siteId}/site-dna
```

Response:
```json
{
  "brand_summary": "...",
  "target_audiences": ["..."],
  "pain_points": ["..."],
  "solutions_themes": ["..."],
  "tone_keywords": ["nuchter", "praktisch", "deskundig"],
  "avoid_words": ["revolutionair", "uniek", "beste"],
  "proof_points": ["..."],
  "compliance_notes": ["..."],
  "generated_at": "2026-01-19T12:00:00"
}
```

### Get Ingest Stats
```bash
GET /api/sites/{siteId}/ingest-stats
```

Response:
```json
{
  "site_id": "...",
  "pages_count": 43,
  "last_crawl": "2026-01-19T12:00:00",
  "chunks_count": 287,
  "site_dna_generated_at": "2026-01-19T12:00:00"
}
```

## Gebruik in Blog Generatie

Het systeem automatisch haalt website context op als `site_id` wordt meegegeven:

```python
from generator.draft_builder import build_draft

draft = build_draft(
    topic="Hoe kies je de juiste software",
    audience={...},
    tone_of_voice={...},
    seo={...},
    brand={...},
    site_id="abc-123"  # <-- website context wordt automatisch gebruikt
)
```

Het systeem:
1. Haalt Site DNA op (brand identity)
2. Selecteert 6 meest relevante chunks op basis van topic/keywords
3. Voegt context toe aan GPT prompt
4. Genereert blog die consistent is met website

## Modules

### `context/crawler.py`
- Respecteert robots.txt
- Throttling (1-2 req/sec)
- Deduplikatie op content hash
- URL normalisatie en filtering

### `context/extractor.py`
- Gebruikt trafilatura voor clean text extraction
- Chunking per H2-sectie (max 1000 tokens)
- Page type detection (landing, service, blog, etc.)

### `context/site_dna.py`
- Genereert "Site DNA" met GPT
- Selecteert priority pages (landing, about, services)
- Extraheert tone, USPs, pain points, proof points

### `context/context_retrieval.py`
- Keyword-based relevance scoring
- Selecteert top-k meest relevante chunks
- Boost voor service/landing pages

### `context/ingest.py`
- Orkestreert hele ingest proces
- Crawl → Extract → Chunk → DNA generation

## Installatie

```bash
pip install -r requirements.txt
python -c "from db import init_db; init_db()"
```

## Workflow

### 1. Connect site
```bash
POST /api/sites/connect
{
  "wpBaseUrl": "https://example.com",
  "wpUsername": "admin",
  "wpApplicationPassword": "..."
}
```

### 2. Crawl website (eenmalig of periodiek)
```bash
POST /api/sites/{siteId}/crawl
{
  "maxDepth": 3,
  "maxPages": 50
}
```

Dit duurt ~1 minuut per 50 pagina's.

### 3. Generate blog (gebruikt automatisch website context)
```bash
POST /api/posts/generate
{
  "siteId": "...",
  "topic": "...",
  "audience": {...},
  ...
}
```

## Best Practices

### Crawl Frequency
- Initieel: bij onboarding
- Daarna: wekelijks of bij belangrijke site updates

### Seed URLs
Geef kernpagina's mee voor beste resultaten:
- Homepage
- Diensten/producten
- About/team
- Pricing
- FAQ
- 2-3 best practices blogs

### Max Depth & Pages
- Depth 2-3: genoeg voor de meeste sites
- Pages 30-50: captures belangrijkste content
- Te veel pagina's = ruis

### Site DNA Refresh
- Automatisch na elke crawl
- Genereert compacte brand identity
- Gebruikt priority pages (landing, about, services eerst)

## Voordelen

✅ **Consistente tone** - Volgt tone keywords uit Site DNA
✅ **Geen hallucinaties** - Alleen claims uit gescrapete content
✅ **Relevante context** - Top-k relevante snippets per blog
✅ **Schaalbaar** - Chunk-based retrieval, geen volledige pagina's
✅ **SEO-proof** - Interne links naar échte pagina's

## Toekomstige Uitbreidingen

- **Embeddings** - Vector-based retrieval i.p.v. keywords
- **Incremental crawl** - Alleen gewijzigde pagina's
- **Sitemap parsing** - Efficiëntere URL discovery
- **CMS integration** - Direct uit WordPress database
