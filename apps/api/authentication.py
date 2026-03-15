"""
API Authentication
==================
Custom DRF authentication backend for submission API keys.

SubmissionAPIKeyAuthentication:
  - Reads the key from the Authorization header: ``Authorization: ApiKey <key>``
  - Hashes it and looks up SubmissionAPIKey using hmac.compare_digest
  - Returns (submission, key_obj) as the DRF user/auth pair
  - Revoked or invalid keys return the same AuthenticationFailed — no state leakage
"""

import logging

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

logger = logging.getLogger(__name__)


class SubmissionAPIKeyAuthentication(BaseAuthentication):
    """
    Authenticate requests that carry an ``Authorization: ApiKey <key>`` header.

    On success, sets:
      - ``request.user`` to the associated ``ServiceSubmission`` instance
      - ``request.auth`` to the ``SubmissionAPIKey`` instance

    Permissions (in api/permissions.py) enforce that the authenticated
    submission matches the requested resource.
    """

    keyword = "ApiKey"

    def authenticate(self, request: Request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None  # Not our scheme — let other authenticators try

        plaintext = auth_header[len(self.keyword) + 1 :].strip()
        if not plaintext:
            raise AuthenticationFailed("API key is empty.")

        from apps.submissions.models import SubmissionAPIKey

        key_obj, authenticated = SubmissionAPIKey.verify(plaintext)

        if not authenticated:
            # Identical response for invalid key and revoked key — no leakage
            logger.warning(
                "API authentication failed",
                extra={"key_hint": plaintext[:8] + "..."},
            )
            raise AuthenticationFailed("Invalid or revoked API key.")

        # Return (user, auth) — DRF convention.
        # We use the submission as the "user" object so permissions can check it.
        return (key_obj.submission, key_obj)

    def authenticate_header(self, request: Request) -> str:
        return self.keyword
