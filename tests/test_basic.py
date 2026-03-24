"""
Basic tests to verify app structure and imports
"""

from src.context.ingest import _upsert_scraped_page
from src.db import _delete_context_site_related_data


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


def test_upsert_scraped_page_reuses_page_id_and_clears_chunks():
    """Existing pages should be updated in place before chunks are recreated."""

    class FakeCursor:
        def __init__(self):
            self.lastrowid = 42
            self.calls = []

        def execute(self, query, params):
            self.calls.append((query, params))

    cursor = FakeCursor()
    page_data = {
        'url': 'https://example.com/page',
        'canonical_url': 'https://example.com/page',
        'title': 'Voorbeeld',
        'status_code': 200,
        'fetched_at': '2026-03-24T10:00:00',
        'content_hash': 'abc123'
    }
    extracted = {
        'clean_text': 'Tekst',
        'headings': ['Kop'],
        'page_type': 'article'
    }

    page_id = _upsert_scraped_page(
        cursor=cursor,
        site_id='site-1',
        site_type='context',
        page_data=page_data,
        extracted=extracted
    )

    assert page_id == 42
    assert len(cursor.calls) == 2
    assert 'ON DUPLICATE KEY UPDATE' in cursor.calls[0][0]
    assert 'LAST_INSERT_ID(id)' in cursor.calls[0][0]
    assert cursor.calls[1] == (
        'DELETE FROM page_chunks WHERE page_id = %s', (42,))


def test_delete_context_site_related_data_uses_child_first_order():
    """Context cleanup should remove child rows before parent pages."""

    class FakeCursor:
        def __init__(self):
            self.calls = []

        def execute(self, query, params):
            self.calls.append((query, params))

    cursor = FakeCursor()

    _delete_context_site_related_data(cursor, user_id=7, days_old=30)

    assert len(cursor.calls) == 3
    assert 'DELETE pc FROM page_chunks pc' in cursor.calls[0][0]
    assert 'DELETE sp FROM scraped_pages sp' in cursor.calls[1][0]
    assert 'DELETE sd FROM site_dna sd' in cursor.calls[2][0]
    assert cursor.calls[0][1] == (7, 30)
    assert cursor.calls[1][1] == (7, 30)
    assert cursor.calls[2][1] == (7, 30)
