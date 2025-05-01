"""Authentication for metric producers via the ``X-Source-Key`` header."""
from __future__ import annotations

import secrets

from rest_framework import authentication, exceptions

from .models import Source

HEADER = "HTTP_X_SOURCE_KEY"


class SourcePrincipal:
    """Minimal user-like object so DRF permission checks work for source-authenticated calls."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, source: Source) -> None:
        self.source = source

    def __str__(self) -> str:
        return f"source:{self.source.slug}"


class SourceKeyAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        key = request.META.get(HEADER)
        if not key:
            return None
        source = Source.objects.filter(api_key=key).first()
        # Compare in constant time even after the lookup to avoid trivially leaking key prefixes.
        if source is None or not secrets.compare_digest(source.api_key, key):
            raise exceptions.AuthenticationFailed("invalid source key")
        if not source.is_active:
            raise exceptions.AuthenticationFailed("source is disabled")
        return SourcePrincipal(source), source

    def authenticate_header(self, request) -> str:
        return "X-Source-Key"
