"""
backends.py — PlaceMe AI
Custom authentication backend that accepts either username OR email.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailOrUsernameBackend(ModelBackend):
    """
    Authenticate with username OR email + password.
    Falls back to Django's standard ModelBackend behaviour for everything else
    (permissions, is_active check, etc.).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        # Try username first (exact, case-insensitive)
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            user = None

        # If no match, try email (case-insensitive)
        if user is None:
            try:
                user = User.objects.get(email__iexact=username)
            except User.DoesNotExist:
                return None
            except User.MultipleObjectsReturned:
                # Multiple accounts share this email — refuse to guess
                return None

        # Check password and active status
        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
