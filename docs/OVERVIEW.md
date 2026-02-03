# SME Blog Platform - Project Overzicht

## 📋 Versie Informatie
- **Versie**: 1.0.0
- **Laatste Update**: February 2026
- **Platform**: Python 3.9+ / Flask
- **Doelgroep**: MKB (Kleine Ondernemingen)

## 🎯 Doel

Een professioneel, gebruiksvriendelijk platform voor kleine bedrijven om automatisch hoogwaardige blog content te genereren en direct naar WordPress te publiceren. Het systeem gebruikt AI (OpenAI & Gemini) om content te creëren die perfect aansluit bij de brand identity en doelgroep.

## 🏗️ Technische Stack

### Backend
- **Framework**: Flask 3.x
- **Database**: MySQL 5.7+
- **Authentication**: Flask-Login + Bcrypt
- **Encryption**: Cryptography (Fernet)

### AI & Content
- **Text Generation**: OpenAI GPT-4o
- **Image Generation**: Google Gemini 2.0
- **Content Analysis**: Custom algorithms + OpenAI

### Frontend
- **Templates**: Jinja2
- **Styling**: Custom CSS (Roboto font)
- **JavaScript**: Vanilla ES6+

### Integration
- **WordPress**: REST API + Application Passwords
- **SEO**: Yoast SEO API
- **Multilingual**: Polylang API

## 📁 Volledige Structuur

```
blogproject/
│
├── run.py                      # Main entry point
├── requirements.txt            # Python dependencies
├── README.md                   # Main documentation
├── .gitignore                 # Git ignore rules
│
├── src/                        # Application source code
│   ├── __init__.py            # Package initialization
│   ├── app.py                 # Flask application & routes
│   ├── auth.py                # User authentication
│   ├── config.py              # Configuration (gitignored)
│   ├── config.example.py      # Config template
│   ├── crypto_utils.py        # Encryption utilities
│   ├── db.py                  # Database operations
│   ├── models.py              # Data models
│   ├── wp_client.py           # WordPress REST API client
│   │
│   ├── context/               # Website analysis & content extraction
│   │   ├── __init__.py
│   │   ├── crawler.py         # Website crawler
│   │   ├── extractor.py       # Content extractor
│   │   ├── ingest.py          # Orchestrator
│   │   ├── site_dna.py        # Brand identity extraction
│   │   ├── context_retrieval.py # Context management
│   │   └── README.md          # Context module docs
│   │
│   ├── generator/             # Content generation
│   │   ├── __init__.py
│   │   ├── draft_builder.py   # Orchestrator
│   │   ├── text_openai.py     # Text generation (OpenAI)
│   │   └── image_gemini.py    # Image generation (Gemini)
│   │
│   └── jobs/                  # Background job processing
│       ├── __init__.py
│       ├── queue.py           # Job queue management
│       ├── worker.py          # Background worker
│       └── publish_job.py     # Publish job implementation
│
├── static/                    # Frontend assets
│   ├── css/
│   │   ├── main.css          # Main stylesheet (imports all)
│   │   ├── colors.css        # Color system & variables
│   │   ├── base.css          # Base styles & typography
│   │   ├── components.css    # UI components
│   │   └── layout.css        # Layout & structure
│   └── js/
│       ├── app.js            # Main application logic
│       ├── api.js            # API communication
│       └── ui.js             # UI interactions
│
├── templates/                 # HTML templates (Jinja2)
│   ├── index.html            # Landing page
│   ├── login.html            # Login page
│   ├── register.html         # Registration page
│   └── dashboard.html        # Main dashboard
│
├── tests/                     # Test suite
│   ├── __init__.py
│   ├── conftest.py           # Test configuration
│   └── test_basic.py         # Basic tests
│
└── docs/                      # Documentation
    ├── INSTALLATION.md        # Installation guide
    ├── DEVELOPMENT.md         # Development guide
    └── OVERVIEW.md           # This file
```

## 🔄 Data Flow

### 1. WordPress Site Connection
```
User Input → Flask Route → Validation → WordPress API Test → 
Credential Encryption → Database Storage → Success Response
```

### 2. Website Analysis
```
Site URL → Crawler → Content Extraction → 
AI Analysis (Brand DNA) → Database Storage
```

### 3. Blog Post Generation
```
User Request → Draft Builder → OpenAI (Text) → Gemini (Image) → 
Preview → Job Queue → Background Worker → WordPress Publish → 
SEO Meta (Yoast) → Multilang Linking (Polylang)
```

## 🔐 Security Features

### Credential Protection
- **Encryption**: Fernet symmetric encryption voor WordPress credentials
- **Master Key**: 32+ character key voor encryption/decryption
- **Storage**: Encrypted credentials in MySQL database

### Authentication
- **Session Management**: Flask-Login sessions
- **Password Hashing**: Bcrypt met salt
- **Route Protection**: @login_required decorator

### API Security
- **WordPress**: Application Passwords (OAuth-like)
- **Input Validation**: Type checking & sanitization
- **SQL Injection**: Parameterized queries
- **XSS Protection**: Jinja2 auto-escaping

## 🎨 Design System

### Color Palette
- **Primary**: #E8F5E9 (Light Green) - Achtergrond, kalmte
- **Secondary**: #091E16 (Dark Forest) - Tekst headers, professionaliteit
- **Text**: #333333 (Charcoal) - Main text, leesbaarheid
- **Accent**: #00C853 (Vivid Green) - CTAs, highlights, conversie

### Typography
- **Font Family**: Roboto (Google Fonts)
- **Weights**: 300, 400, 500, 700
- **Monospace**: Roboto Mono (code blocks)

### Components
- **Border Radius**: 5px (consistent rounded corners)
- **Shadows**: Subtle elevation system
- **Buttons**: Accent green met hover states
- **Forms**: Clean, minimal styling

## 📊 Database Schema

### Main Tables

**users**
- id, username, email, password_hash, created_at, is_active

**sites**
- id, user_id, site_url, site_name, wp_username, wp_password_encrypted, created_at

**posts**
- id, site_id, wp_post_id, title, content, status, language, created_at

**site_context**
- id, site_id, brand_name, tone_of_voice, target_audience, context_data

**jobs**
- id, job_type, payload, status, created_at, updated_at, error_message

## 🚀 Key Features

### Voor Gebruikers
- ✅ Eenvoudige WordPress connectie
- ✅ Automatische website analyse
- ✅ AI-gedreven content generatie
- ✅ One-click publicatie
- ✅ SEO optimalisatie
- ✅ Multilingual support

### Voor Developers
- ✅ Clean architecture (src/ structuur)
- ✅ Type hints & docstrings
- ✅ Comprehensive error handling
- ✅ Logging op alle niveaus
- ✅ Test framework ready
- ✅ Easy deployment

## 🔧 Configuration

### Environment Variables (config.py)
```python
# Required
DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
OPENAI_API_KEY
GEMINI_API_KEY
MASTER_KEY (32+ chars)

# Optional
APP_HOST = "0.0.0.0"
APP_PORT = 5000
OPENAI_TEXT_MODEL = "gpt-4o"
GEMINI_IMAGE_MODEL = "gemini-2.0-flash-exp"
```

## 📈 Performance

### Optimization Strategies
- Background job processing voor lange taken
- Database connection pooling
- Efficient credential caching
- Minimal API calls met retry logic
- Asynchronous WordPress publishing

## 🐛 Debugging

### Log Levels
- **DEBUG**: Gedetailleerde info voor development
- **INFO**: Algemene flow events
- **WARNING**: Unexpected maar handled situations
- **ERROR**: Errors die recovery mogelijk maken
- **CRITICAL**: System-breaking errors

### Common Issues & Solutions
Zie `docs/DEVELOPMENT.md` troubleshooting sectie

## 🚀 Deployment

### Development
```bash
python run.py
```

### Production
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "src.app:app"
```

### Requirements
- Python 3.9+
- MySQL 5.7+
- 512MB RAM minimum
- SSL certificate (productie)

## 📝 TODO / Roadmap

### Fase 1 (Current) - MVP
- [x] Core Flask app structuur
- [x] WordPress integratie
- [x] Basic content generatie
- [x] User authentication
- [x] Website analyse

### Fase 2 - Improvements
- [ ] Advanced SEO analysis
- [ ] Content scheduling
- [ ] Analytics dashboard
- [ ] Bulk post generation
- [ ] Template library

### Fase 3 - Scale
- [ ] Multi-site management
- [ ] Team collaboration
- [ ] API rate limiting
- [ ] Caching layer
- [ ] Admin panel

## 🤝 Contributing

Zie `docs/DEVELOPMENT.md` voor development guidelines en code style.

## 📄 Licentie

Proprietary - Alle rechten voorbehouden

## 📞 Support

Voor vragen of issues, neem contact op met het development team.

---

**Laatste update**: February 2026  
**Maintained by**: Development Team
