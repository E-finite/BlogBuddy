"""
SME Blog Platform - Application Entry Point

This is the main entry point for running the Flask application.
Start the app by running: python run.py
"""
import logging
from src import config
from src.app import app
from src.generator.image_gemini import validate_vertex_auth_startup
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(
        f"Starting SME Blog Platform on {config.APP_HOST}:{config.APP_PORT}")
    logger.info("Press CTRL+C to quit")

    try:
        validate_vertex_auth_startup()
    except Exception as e:
        if config.STRICT_VERTEX_STARTUP_CHECK:
            raise
        logger.warning(
            "Vertex startup auth check failed; app continues with fallback image providers. "
            f"Set STRICT_VERTEX_STARTUP_CHECK=true to fail fast. Details: {e}"
        )

    app.run(
        host=config.APP_HOST,
        port=config.APP_PORT,
        debug=False
    )
