"""Tests for the password reset flow."""

import src.app as app_module


def test_forgot_password_page_renders(client):
    """Forgot-password page should render for logged-out users."""
    response = client.get('/forgot-password')

    assert response.status_code == 200
    assert b'Wachtwoord vergeten' in response.data


def test_forgot_password_existing_email_creates_token_and_sends_mail(client, monkeypatch):
    """Known emails should create a token and trigger a reset email."""
    recorded = {}

    monkeypatch.setattr(app_module.db, 'get_user_by_email', lambda email: {
        'id': 12,
        'email': 'user@example.com',
        'is_active': 1,
    })

    def fake_create_password_reset_token(user_id, token, expires_at):
        recorded['user_id'] = user_id
        recorded['token'] = token
        recorded['expires_at'] = expires_at
        return True

    def fake_build_reset_password_url(token, request_base_url):
        recorded['request_base_url'] = request_base_url
        return f'https://example.com/reset-password/{token}'

    def fake_send_password_reset_email(recipient_email, reset_url):
        recorded['recipient_email'] = recipient_email
        recorded['reset_url'] = reset_url
        return True, ''

    monkeypatch.setattr(
        app_module.db, 'create_password_reset_token', fake_create_password_reset_token)
    monkeypatch.setattr(app_module, 'build_reset_password_url',
                        fake_build_reset_password_url)
    monkeypatch.setattr(app_module, 'send_password_reset_email',
                        fake_send_password_reset_email)

    response = client.post(
        '/forgot-password',
        data={'email': 'User@Example.com'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Als dit e-mailadres bekend is, ontvang je een reset link.' in response.data
    assert recorded['user_id'] == 12
    assert recorded['recipient_email'] == 'user@example.com'
    assert recorded['reset_url'].startswith(
        'https://example.com/reset-password/')
    assert recorded['token']
    assert recorded['request_base_url'] == 'http://localhost/'


def test_forgot_password_unknown_email_returns_neutral_message(client, monkeypatch):
    """Unknown emails should not reveal account existence."""
    monkeypatch.setattr(app_module.db, 'get_user_by_email', lambda email: None)
    monkeypatch.setattr(
        app_module.db,
        'create_password_reset_token',
        lambda *args, **kwargs: (_ for _ in ()
                                 ).throw(AssertionError('should not create token')),
    )
    monkeypatch.setattr(
        app_module,
        'send_password_reset_email',
        lambda *args, **kwargs: (_ for _ in ()
                                 ).throw(AssertionError('should not send mail')),
    )

    response = client.post(
        '/forgot-password',
        data={'email': 'unknown@example.com'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Als dit e-mailadres bekend is, ontvang je een reset link.' in response.data


def test_reset_password_invalid_token_redirects_to_login(client, monkeypatch):
    """Invalid tokens should be rejected."""
    monkeypatch.setattr(
        app_module.db, 'validate_password_reset_token', lambda token: None)

    response = client.get('/reset-password/bad-token', follow_redirects=True)

    assert response.status_code == 200
    assert b'Deze reset link is ongeldig of verlopen.' in response.data
    assert b'Inloggen' in response.data


def test_reset_password_success_updates_hash_and_deletes_token(client, monkeypatch):
    """A valid token should allow storing a new password exactly once."""
    recorded = {}

    monkeypatch.setattr(app_module.db, 'validate_password_reset_token', lambda token: {
        'user_id': 33,
        'email': 'user@example.com',
        'username': 'tester',
        'is_active': 1,
    })

    def fake_update_user_password_hash(user_id, password_hash):
        recorded['user_id'] = user_id
        recorded['password_hash'] = password_hash
        return True

    def fake_delete_password_reset_token(token):
        recorded['deleted_token'] = token
        return True

    monkeypatch.setattr(
        app_module.db, 'update_user_password_hash', fake_update_user_password_hash)
    monkeypatch.setattr(
        app_module.db, 'delete_password_reset_token', fake_delete_password_reset_token)

    response = client.post(
        '/reset-password/valid-token',
        data={
            'new_password': 'nieuwveilig123',
            'confirm_password': 'nieuwveilig123',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Je wachtwoord is aangepast. Je kunt nu inloggen.' in response.data
    assert recorded['user_id'] == 33
    assert recorded['deleted_token'] == 'valid-token'
    assert app_module.bcrypt.check_password_hash(
        recorded['password_hash'], 'nieuwveilig123')


def test_reset_password_rejects_mismatched_passwords(client, monkeypatch):
    """The reset form should reject mismatched passwords."""
    monkeypatch.setattr(app_module.db, 'validate_password_reset_token', lambda token: {
        'user_id': 33,
        'email': 'user@example.com',
        'username': 'tester',
        'is_active': 1,
    })
    monkeypatch.setattr(
        app_module.db,
        'update_user_password_hash',
        lambda *args, **kwargs: (_ for _ in ()
                                 ).throw(AssertionError('should not update password')),
    )

    response = client.post(
        '/reset-password/valid-token',
        data={
            'new_password': 'nieuwveilig123',
            'confirm_password': 'anderwachtwoord',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Wachtwoorden komen niet overeen.' in response.data
