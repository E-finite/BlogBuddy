"""Configuration management for the WordPress blog generator service."""
import os
from pathlib import Path

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDXCv2rF5eFwEqma2RpPgEDRI_1eWXuRAg")
MASTER_KEY = os.getenv("MASTER_KEY", "UMDehz2jTMu1rzfaBCEIha6RdlGKYt-dymvwvxWM_qM0byzvz_40UNlpdE_bp9KhfGjmUzTXeM5bOdbW1njOnw")
APP_DB_PATH = os.getenv("APP_DB_PATH", "./data/app.db")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp")

# Ensure data directory exists
Path(APP_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

# Validation
if not MASTER_KEY:
    raise ValueError("MASTER_KEY environment variable is required for encryption")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required")
