"""
SME Blog Platform - Application Entry Point

This is the main entry point for running the Flask application.
Start the app by running: python run.py
"""
import logging
from src import config
from src.app import app
import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info(
        f"Starting SME Blog Platform on {config.APP_HOST}:{config.APP_PORT}")
    logger.info("Press CTRL+C to quit")

    app.run(
        host=config.APP_HOST,
        port=config.APP_PORT,
        debug=False
    )
