"""
Pytest Configuration
====================
Global test fixtures and Django settings overrides.
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Required env vars for tests — minimal safe values
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-for-production")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("REDIS_PASSWORD", "test")
os.environ.setdefault("DEBUG", "true")

import pytest

def pytest_configure(config):
    import django
    django.setup()

@pytest.fixture
def rf():
    from django.test import RequestFactory
    return RequestFactory()
