"""Runtime configuration loaded from .env/environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv


def _to_bool(value: str | None, default: bool = False) -> bool:
	if value is None:
		return default
	return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, default: int) -> int:
	if value is None or value == "":
		return default
	try:
		return int(value)
	except ValueError:
		return default


def _to_float(value: str | None, default: float) -> float:
	if value is None or value == "":
		return default
	try:
		return float(value)
	except ValueError:
		return default


def _to_list(value: str | None) -> list[str]:
	if not value:
		return []
	return [item.strip() for item in value.split(",") if item.strip()]


_ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT_DIR / ".env")

# API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Vertex AI auth/config
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "your-gcp-project-id")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
STRICT_VERTEX_STARTUP_CHECK = _to_bool(
	os.getenv("STRICT_VERTEX_STARTUP_CHECK"),
	default=False,
)

# Ensure google-auth can discover service account from env.
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
	os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv(
		"GOOGLE_APPLICATION_CREDENTIALS", ""
	)

# Database
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = _to_int(os.getenv("MYSQL_PORT"), 3306)
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "blogbot")
MYSQL_CONNECT_TIMEOUT_SECONDS = _to_int(
	os.getenv("MYSQL_CONNECT_TIMEOUT_SECONDS"),
	5,
)
MYSQL_CONNECT_RETRIES = _to_int(os.getenv("MYSQL_CONNECT_RETRIES"), 5)
MYSQL_CONNECT_RETRY_DELAY_SECONDS = _to_float(
	os.getenv("MYSQL_CONNECT_RETRY_DELAY_SECONDS"),
	1.5,
)

# App/security
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = _to_int(os.getenv("APP_PORT"), 8000)
APP_PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "http://localhost:8000")
MASTER_KEY = os.getenv("MASTER_KEY", "replace-with-strong-random-key-min-32-chars")
PASSWORD_RESET_TOKEN_TTL_SECONDS = _to_int(
	os.getenv("PASSWORD_RESET_TOKEN_TTL_SECONDS"),
	3600,
)
ADMIN_EMAILS = _to_list(os.getenv("ADMIN_EMAILS"))

# Mail
MAIL_SERVER = os.getenv("MAIL_SERVER", "")
MAIL_PORT = _to_int(os.getenv("MAIL_PORT"), 587)
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "")
MAIL_USE_TLS = _to_bool(os.getenv("MAIL_USE_TLS"), default=True)
MAIL_USE_SSL = _to_bool(os.getenv("MAIL_USE_SSL"), default=False)

# Models
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")
OPENAI_TRANSLATION_MODEL = os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini")
IMAGEN_MODEL = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
IMAGEN_EDIT_MODEL = os.getenv("IMAGEN_EDIT_MODEL", "imagen-3.0-capability-001")
GEMINI_IMAGE_MODEL = os.getenv(
	"GEMINI_IMAGE_MODEL",
	"gemini-2.0-flash-exp-image-generation",
)

# Optional logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
