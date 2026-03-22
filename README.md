# SME Blog Platform

Een professioneel blog platform voor kleine bedrijven (MKB) met AI-gedreven content generatie en WordPress integratie.

## 🚀 Features

- ✅ WordPress REST API integratie (Application Passwords / Basic Auth)
- ✅ AI Blog generatie met OpenAI (GPT-4o) - doelgroep, tone of voice, SEO optimalisatie
- ✅ Automatische publicatie naar WordPress (draft/scheduled/published)
- ✅ Yoast SEO meta integratie
- ✅ Multi-language support via Polylang (optioneel)
- ✅ Featured image generatie met Gemini
- ✅ Job queue met persistent storage (MySQL)
- ✅ Retry logic met exponential backoff
- ✅ Encrypted credential storage
- ✅ Website analyse en brand identity extractie
- ✅ Gebruikersauthenticatie en sessie management

## 📁 Projectstructuur

```
blogproject/
├── src/                    # Applicatie broncode
│   ├── context/           # Website analyse en content extractie
│   ├── generator/         # Content en afbeelding generatie
│   ├── jobs/              # Achtergrond jobs en queue systeem
│   ├── app.py             # Flask applicatie en routes
│   ├── auth.py            # Authenticatie
│   ├── config.py          # Configuratie (niet in git!)
│   ├── crypto_utils.py    # Encryptie utilities
│   ├── db.py              # Database operaties
│   ├── models.py          # Data modellen
│   └── wp_client.py       # WordPress REST API client
├── static/                # CSS, JavaScript, afbeeldingen
├── templates/             # HTML templates
├── tests/                 # Tests
├── docs/                  # Documentatie
├── run.py                 # Applicatie entry point
└── requirements.txt       # Python dependencies
```

## 🔧 Snelle Start

### 1. Python Environment

```bash
# Python 3.9+ vereist
python --version

# Maak virtual environment
python -m venv .venv

# Activeer venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Installeer dependencies
pip install -r requirements.txt
```

### 2. Configuratie

Gebruik `.env` bestanden voor secrets:

```bash
# Maak lokale env file
copy .env.example .env
```

Vul daarna je credentials in `.env`:

```env
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
MASTER_KEY=your-secure-master-key-min-32-chars
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DATABASE=blogbot
APP_HOST=0.0.0.0
APP_PORT=8000
```

### 3. Applicatie starten

```bash
python run.py
```

De applicatie is nu beschikbaar op `http://localhost:5000`

### 4. WordPress Setup

#### Application Passwords inschakelen

1. Ga naar WordPress Admin → Users → Your Profile
2. Scroll naar "Application Passwords"
3. Maak een nieuwe Application Password aan (bijv. "Blog Generator Bot")
4. Kopieer de gegenereerde password (format: `xxxx xxxx xxxx xxxx`)
5. Gebruik deze password in combinatie met je WordPress username

#### Vereiste WordPress Plugins

De service verwacht de volgende custom endpoints:

1. **Yoast SEO Meta API** (`/wp-json/yoast-api/v1/update-meta`)
2. **Polylang Linker** (`/wp-json/my-plugin/v1/link-translations`)

**Note**: Als deze plugins niet actief zijn, zal de service een warning loggen maar doorgaan met publicatie.

#### Permalink Settings

Zorg dat WordPress permalinks zijn ingeschakeld (Settings → Permalinks). De REST API vereist dit.

## 📖 Gebruik

Bezoek `http://localhost:5000` en log in met je account. De web interface biedt:

- WordPress site beheer en connectie
- Blog post generatie met AI
- Dashboard met statistieken
- Settings en configuratie

## 🔌 API Endpoints

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
