"""
Basic tests to verify app structure and imports
"""


def test_app_imports():
    """Test that core modules can be imported."""
    from src import app
    from src import auth
    from src import db
    from src import config
    assert app is not None
    assert auth is not None
    assert db is not None
    assert config is not None


def test_app_creation(client):
    """Test that Flask app is created successfully."""
    response = client.get('/')
    assert response.status_code == 200


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
