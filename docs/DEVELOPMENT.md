# SME Blog Platform - Development Guide

## Ontwikkelomgeving Setup

### Vereisten
- Python 3.9+
- MySQL 5.7+
- Git
- Code editor (VS Code aanbevolen)

### Eerste keer setup

```bash
# Clone repository
git clone <repository-url>
cd blogproject

# Virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Dependencies
pip install -r requirements.txt

# Config
cp src/config.example.py src/config.py
# Bewerk src/config.py met je credentials
```

## Projectstructuur

### Hoofdmappen

- **src/** - Alle applicatie code
  - **context/** - Website crawling en analyse
  - **generator/** - AI content generatie
  - **jobs/** - Background job processing
- **static/** - Frontend assets (CSS, JS)
- **templates/** - HTML templates (Jinja2)
- **tests/** - Unit en integratie tests
- **docs/** - Documentatie

### Import Convention

Alle imports gebruiken de `src.` prefix:

```python
# Correct ✅
from src import config
from src.auth import User
from src.generator.draft_builder import build_draft

# Incorrect ❌
import config
from auth import User
```

## Development Workflow

### 1. Feature Development

```bash
# Maak een feature branch
git checkout -b feature/jouw-feature-naam

# Ontwikkel je feature in src/
# Schrijf tests in tests/

# Run tests
pytest tests/

# Commit changes
git add .
git commit -m "feat: beschrijving van feature"
git push origin feature/jouw-feature-naam
```

### 2. Running the App

```bash
# Development mode
python run.py

# De app draait op http://localhost:5000
```

### 3. Database Migrations

```bash
# Als je database schema wijzigingen hebt:
# - Update src/db.py met nieuwe functies
# - Test handmatig of maak een migratie script in docs/migrations/
```

## Code Style

### Python Style Guide
- Follow PEP 8
- Use type hints waar mogelijk
- Docstrings voor alle functies/classes

```python
def example_function(param: str, optional: int = 0) -> dict:
    """
    Kort beschrijving wat de functie doet.
    
    Args:
        param: Beschrijving van parameter
        optional: Optionele parameter beschrijving
        
    Returns:
        Dict met resultaat
    """
    return {"result": param}
```

### Frontend Style
- CSS: Gebruik de bestaande CSS variabelen in colors.css
- JavaScript: ES6+ syntax
- Gebruik semantic HTML

## Testing

### Run Tests

```bash
# Alle tests
pytest

# Specifieke test file
pytest tests/test_basic.py

# Met coverage
pytest --cov=src tests/

# Verbose output
pytest -v
```

### Test Structuur

```python
def test_functie_naam():
    """Test beschrijving."""
    # Arrange
    input_data = {...}
    
    # Act
    result = functie_om_te_testen(input_data)
    
    # Assert
    assert result == expected_value
```

## Debugging

### VS Code Launch Configuration

Maak `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Flask",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/run.py",
      "console": "integratedTerminal"
    }
  ]
}
```

### Logging

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Debug info")
logger.info("Info message")
logger.warning("Warning")
logger.error("Error occurred")
```

## Database

### Schema Updates

1. Update functies in `src/db.py`
2. Test handmatig in MySQL
3. Documenteer in `docs/migrations/`

### Query Guidelines

- Gebruik parameterized queries (SQL injection preventie)
- Sluit altijd connections af
- Gebruik context managers waar mogelijk

```python
conn = get_db_connection()
try:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM table WHERE id = %s", (id,))
    result = cursor.fetchone()
finally:
    cursor.close()
    conn.close()
```

## API Development

### Adding New Endpoints

1. Voeg route toe in `src/app.py`
2. Gebruik type hints en validatie
3. Return JSON responses
4. Log errors

```python
@app.route("/api/nieuwe-endpoint", methods=["POST"])
@login_required
def nieuwe_endpoint():
    """Endpoint beschrijving."""
    try:
        data = request.get_json()
        # Validatie
        if not data.get("required_field"):
            return jsonify({"error": "Missing field"}), 400
        
        # Verwerk data
        result = process_data(data)
        
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error in endpoint: {e}")
        return jsonify({"error": str(e)}), 500
```

## Security

### Best Practices

- ✅ Gebruik `@login_required` voor protected routes
- ✅ Valideer alle user input
- ✅ Gebruik parameterized queries
- ✅ Hash passwords met bcrypt
- ✅ Encrypt credentials met crypto_utils
- ✅ Nooit credentials in logs
- ✅ HTTPS in productie

### Credential Management

```python
from src import crypto_utils

# Encrypt
encrypted = crypto_utils.encrypt_credential("sensitive_data")

# Decrypt
decrypted = crypto_utils.decrypt_credential(encrypted)
```

## Performance

### Optimization Tips

- Cache database queries waar mogelijk
- Gebruik background jobs voor lange taken
- Minimize API calls
- Optimize database indices
- Monitor memory usage

## Deployment

Zie `docs/INSTALLATION.md` voor deployment instructies.

## Troubleshooting

### Common Issues

**Import Error: No module named 'src'**
```bash
# Zorg dat je run.py gebruikt of sys.path correct is
python run.py  # ✅
python src/app.py  # ❌
```

**Database Connection Error**
```bash
# Check config.py credentials
# Verify MySQL is running
# Test connection: mysql -u user -p
```

**API Key Errors**
```bash
# Verify config.py has valid keys
# Check .gitignore excludes config.py
```

## Resources

- Flask Documentation: https://flask.palletsprojects.com/
- OpenAI API: https://platform.openai.com/docs
- WordPress REST API: https://developer.wordpress.org/rest-api/

## Support

Voor vragen of issues, maak een ticket aan in de issue tracker.
