# SME Blog Platform - Installatie & Setup

## Overzicht
Een professioneel blog platform voor kleine bedrijven (MKB) met geautomatiseerde content generatie en WordPress integratie.

## Projectstructuur

```
blogproject/
├── src/                    # Applicatie broncode
│   ├── context/           # Website analyse en content extractie
│   ├── generator/         # Content en afbeelding generatie
│   ├── jobs/              # Achtergrond jobs en queue systeem
│   ├── app.py             # Flask applicatie en routes
│   ├── auth.py            # Authenticatie en gebruikersbeheer
│   ├── config.py          # Configuratie (niet in git!)
│   ├── crypto_utils.py    # Encryptie utilities
│   ├── db.py              # Database operaties
│   ├── models.py          # Data modellen
│   └── wp_client.py       # WordPress REST API client
├── static/                # CSS, JavaScript, afbeeldingen
│   ├── css/
│   └── js/
├── templates/             # HTML templates
├── tests/                 # Unit en integratie tests
├── docs/                  # Project documentatie
├── run.py                 # Applicatie entry point
├── requirements.txt       # Python dependencies
└── README.md             # Project documentatie

```

## Vereisten

- Python 3.9+
- MySQL database
- OpenAI API key
- Google Gemini API key

## Installatie

### 1. Clone het repository
```bash
git clone <repository-url>
cd blogproject
```

### 2. Maak een virtual environment
```bash
python -m venv .venv
```

### 3. Activeer de virtual environment

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 4. Installeer dependencies
```bash
pip install -r requirements.txt
```

### 5. Configuratie

Maak een `src/config.py` bestand met de volgende inhoud:

```python
# Database configuratie
DB_HOST = "localhost"
DB_USER = "your_db_user"
DB_PASSWORD = "your_db_password"
DB_NAME = "blogplatform"

# API Keys
OPENAI_API_KEY = "your_openai_api_key"
GEMINI_API_KEY = "your_gemini_api_key"

# Applicatie configuratie
APP_HOST = "0.0.0.0"
APP_PORT = 5000

# Security
MASTER_KEY = "your_secure_master_key_here"  # Minimaal 32 karakters
```

### 6. Database setup

```sql
CREATE DATABASE blogplatform;
-- Run database schema script
```

## Applicatie starten

```bash
python run.py
```

De applicatie is nu beschikbaar op `http://localhost:5000`

## Development

### Code structuur
- Alle applicatie code staat in `src/`
- Imports gebruiken de `src.` prefix (bijv. `from src.auth import User`)
- Static files en templates staan in de root voor Flask compatibiliteit

### Tests uitvoeren
```bash
pytest tests/
```

### Code style
```bash
# Format code
black src/

# Lint
flake8 src/
```

## Deployment

### Production checklist
- [ ] Update `config.py` met productie credentials
- [ ] Zet `debug=False` in run.py
- [ ] Configureer HTTPS
- [ ] Setup database backups
- [ ] Configureer logging
- [ ] Setup monitoring

### WSGI Server (productie)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "src.app:app"
```

## Features

- 🔐 Gebruikersauthenticatie met sessie management
- 🌐 WordPress site connectie en beheer
- 🤖 AI-gedreven content generatie (OpenAI)
- 🎨 Geautomatiseerde afbeelding generatie (Gemini)
- 📊 Website analyse en brand identity extractie
- 🚀 Achtergrond job processing
- 🔒 Veilige credential opslag met encryptie

## Support

Voor vragen of problemen, zie de documentatie in de `docs/` directory.

## Licentie

Proprietary - Alle rechten voorbehouden
