"""
Configuration template for SME Blog Platform
Copy this file to config.py and fill in your credentials
"""

# Database Configuration
DB_HOST = "localhost"
DB_USER = "your_database_user"
DB_PASSWORD = "your_database_password"
DB_NAME = "blogplatform"
DB_PORT = 3306

# API Keys
OPENAI_API_KEY = "sk-your-openai-api-key-here"
GEMINI_API_KEY = "your-gemini-api-key-here"

# Application Settings
APP_HOST = "0.0.0.0"
APP_PORT = 5000

# Security
# IMPORTANT: Use a strong, unique key of at least 32 characters
# This key is used for encrypting WordPress credentials
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
MASTER_KEY = "your-secure-master-key-min-32-chars-here"

# Optional: Model Configuration
OPENAI_TEXT_MODEL = "gpt-4o"  # or "gpt-4", "gpt-3.5-turbo"
GEMINI_IMAGE_MODEL = "gemini-2.0-flash-exp"

# Optional: Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
