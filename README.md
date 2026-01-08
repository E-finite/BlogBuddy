# WordPress Blog Generator MVP

Een Python Flask service die automatisch blog posts genereert met OpenAI en publiceert naar WordPress, inclusief Yoast SEO meta en multi-language support via Polylang.

## Features

- ✅ WordPress REST API integratie (Application Passwords / Basic Auth)
- ✅ Blog generatie met OpenAI (GPT-4o) - doelgroep, tone of voice, SEO regels
- ✅ Automatische publicatie naar WordPress (draft/scheduled/published)
- ✅ Yoast SEO meta via custom endpoint
- ✅ Multi-language posts via Polylang endpoint (optioneel)
- ✅ Featured image generatie met Gemini (optioneel)
- ✅ Job queue met persistent storage (SQLite)
- ✅ Retry logic met exponential backoff
- ✅ Encrypted credential storage

## Setup

### 1. Python Environment

```bash
# Python 3.11+ vereist
python --version

# Maak virtual environment
python -m venv venv

# Activeer venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Installeer dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Maak een `.env` bestand of exporteer de volgende variabelen:

```bash
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="..."
export MASTER_KEY="your-secret-encryption-key-min-32-chars"
export APP_DB_PATH="./data/app.db"
export APP_HOST="0.0.0.0"
export APP_PORT="8000"
export OPENAI_TEXT_MODEL="gpt-4o"  # Optioneel, default: gpt-4o
export GEMINI_IMAGE_MODEL="gemini-2.0-flash-exp"  # Optioneel
```

**BELANGRIJK**: `MASTER_KEY` moet minimaal 32 karakters zijn en wordt gebruikt voor encryptie van WordPress credentials. Gebruik een sterke, unieke key.

### 3. WordPress Setup

#### Application Passwords inschakelen

1. Ga naar WordPress Admin → Users → Your Profile
2. Scroll naar "Application Passwords"
3. Maak een nieuwe Application Password aan (bijv. "Blog Generator Bot")
4. Kopieer de gegenereerde password (format: `xxxx xxxx xxxx xxxx`)
5. Gebruik deze password in combinatie met je WordPress username

#### Vereiste WordPress Plugins

De service verwacht de volgende custom endpoints:

1. **Yoast SEO Meta API** (`/wp-json/yoast-api/v1/update-meta`)
   - Plugin moet een endpoint registreren die accepteert:
     ```json
     {
       "post_id": 123,
       "focuskw": "keyword",
       "seo_title": "SEO Title",
       "meta_desc": "Meta description"
     }
     ```

2. **Polylang Linker** (`/wp-json/my-plugin/v1/link-translations`)
   - Plugin moet een endpoint registreren die accepteert:
     ```json
     {
       "translations": {
         "nl": 123,
         "en": 124
       }
     }
     ```

**Note**: Als deze plugins niet actief zijn, zal de service een warning loggen maar doorgaan met publicatie (zonder Yoast/Polylang updates).

#### Permalink Settings

Zorg dat WordPress permalinks zijn ingeschakeld (Settings → Permalinks). De REST API vereist dit.

## Gebruik

### API Server Starten

```bash
python app.py
```

De server draait op `http://localhost:8000` (of zoals geconfigureerd).

### API Endpoints

#### 1. Connect WordPress Site

```bash
curl -X POST http://localhost:8000/api/sites/connect \
  -H "Content-Type: application/json" \
  -d '{
    "wpBaseUrl": "https://example.com",
    "wpUsername": "botuser",
    "wpApplicationPassword": "xxxx xxxx xxxx xxxx"
  }'
```

Response:
```json
{
  "siteId": "uuid",
  "ok": true,
  "wpUser": {
    "id": 1,
    "name": "Bot User"
  }
}
```

#### 2. Generate Blog Post

```bash
curl -X POST http://localhost:8000/api/posts/generate \
  -H "Content-Type: application/json" \
  -d '{
    "siteId": "uuid",
    "topic": "Hoe maak je een WordPress blog?",
    "audience": {
      "market": "kleine ondernemers",
      "level": "beginner",
      "painPoints": ["geen technische kennis"],
      "objections": ["te duur", "te complex"]
    },
    "toneOfVoice": {
      "style": ["nuchter", "direct"],
      "formality": "je",
      "do": ["korte zinnen", "concrete voorbeelden"],
      "dont": ["geen hype", "geen jargon"]
    },
    "seo": {
      "focusKeyword": "wordpress blog maken",
      "secondaryKeywords": ["blog opzetten", "wordpress tutorial"],
      "internalLinkTargets": [
        {"title": "WordPress Hosting", "url": "/hosting"}
      ],
      "metaTitlePattern": "{topic} | {brand}",
      "metaDescMaxLen": 155
    },
    "brand": {
      "name": "My Brand",
      "cta": "Start vandaag nog"
    },
    "language": "nl",
    "status": "draft",
    "multilang": {
      "enabled": false,
      "languages": [],
      "strategy": "translate"
    }
  }'
```

Response:
```json
{
  "draft": {
    "title": "...",
    "slug": "...",
    "excerpt": "...",
    "contentHtml": "<p>...</p>",
    "yoast": {
      "focuskw": "...",
      "seo_title": "...",
      "meta_desc": "..."
    },
    "tags": [...],
    "categories": [...]
  }
}
```

#### 3. Publish Blog Post

```bash
curl -X POST http://localhost:8000/api/posts/publish \
  -H "Content-Type: application/json" \
  -d '{
    "siteId": "uuid",
    "draft": { ... }
  }'
```

Response:
```json
{
  "jobId": "uuid",
  "status": "queued"
}
```

#### 4. Get Job Status

```bash
curl http://localhost:8000/api/jobs/{jobId}
```

Response:
```json
{
  "jobId": "uuid",
  "status": "success",
  "result": {
    "wpPostIds": {
      "default": 123
    },
    "errors": []
  },
  "steps": [...]
}
```

### CLI Demo Script

Gebruik het demo script voor een complete workflow:

```bash
python scripts/publish_demo.py \
  --wpBaseUrl "https://example.com" \
  --wpUsername "botuser" \
  --wpAppPassword "xxxx xxxx xxxx xxxx" \
  --topic "Hoe maak je een WordPress blog?" \
  --focusKeyword "wordpress blog maken" \
  --brandName "My Brand"
```

## Database Schema

De service gebruikt SQLite voor persistent storage:

- **sites**: Opgeslagen WordPress sites met encrypted credentials
- **jobs**: Job queue met status tracking
- **job_steps**: Gedetailleerde stap tracking per job

## Foutafhandeling

### Veelvoorkomende Errors

1. **401/403 Unauthorized**
   - **Oorzaak**: Verkeerde WordPress credentials of onvoldoende permissions
   - **Oplossing**: Controleer username en application password, zorg dat de user editor/author rechten heeft

2. **404 Not Found (REST API)**
   - **Oorzaak**: Permalinks niet ingeschakeld of WordPress REST API uitgeschakeld
   - **Oplossing**: Ga naar Settings → Permalinks en sla op (ook al verander je niets)

3. **404 Not Found (Plugin Endpoints)**
   - **Oorzaak**: Yoast of Polylang plugin endpoints niet actief
   - **Oplossing**: Plugin activeren of custom endpoint registreren. De service gaat door zonder deze features.

4. **429 Too Many Requests**
   - **Oorzaak**: Te veel requests naar WordPress API
   - **Oplossing**: Service retry automatisch met exponential backoff

5. **OpenAI API Errors**
   - **Oorzaak**: Invalid API key, rate limits, of model niet beschikbaar
   - **Oplossing**: Controleer `OPENAI_API_KEY` en model naam

6. **Gemini API Errors**
   - **Oorzaak**: Invalid API key of image generation niet beschikbaar
   - **Oplossing**: Service gaat door zonder featured image als generatie faalt

## Architectuur

```
app.py                    # Flask API server
├── config.py            # Environment config
├── db.py                # SQLite database utilities
├── crypto_utils.py      # Encryption (Fernet)
├── models.py            # Pydantic schemas
├── wp_client.py         # WordPress REST API client
├── generator/
│   ├── text_openai.py   # OpenAI text generation
│   ├── image_gemini.py  # Gemini image generation
│   └── draft_builder.py # Draft orchestration
└── jobs/
    ├── queue.py         # In-process job queue
    ├── worker.py        # Background worker thread
    └── publish_job.py   # Publish job implementation
```

## Security

- WordPress application passwords worden encrypted opgeslagen met Fernet (AES)
- Credentials worden nooit gelogd
- URL validatie voorkomt SSRF attacks
- Input validatie via Pydantic

## Development

### Logging

Logs worden naar stdout geschreven met INFO level. Voor debug, pas `logging.basicConfig` aan in `app.py`.

### Testing

Voor testing, gebruik de CLI demo script of curl commands zoals hierboven beschreven.

## Licentie

MIT

## Support

Voor vragen of issues, check de logs in de console output of database voor job details.
