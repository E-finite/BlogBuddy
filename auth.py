"""Authentication models and utilities."""
from flask_login import UserMixin
from typing import Optional
import db


class User(UserMixin):
    """User model for Flask-Login."""

    def __init__(self, id: int, username: str, email: str, is_active: bool = True):
        self.id = id
        self.username = username
        self.email = email
        self._is_active = is_active

    def get_id(self):
        """Return user ID as string (required by Flask-Login)."""
        return str(self.id)

    @property
    def is_active(self):
        """Return True if user is active."""
        return self._is_active

    @property
    def is_authenticated(self):
        """Return True if user is authenticated."""
        return True

    @property
    def is_anonymous(self):
        """Return True if anonymous user."""
        return False

    @staticmethod
    def get(user_id: int) -> Optional['User']:
        """Get user by ID."""
        user_data = db.get_user_by_id(user_id)
        if user_data:
            return User(
                id=user_data['id'],
                username=user_data['username'],
                email=user_data['email'],
                is_active=bool(user_data.get('is_active', 1))
            )
        return None
