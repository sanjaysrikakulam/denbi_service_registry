"""
Pytest configuration and shared fixtures.

Django settings are handled by config/settings_test.py (see pytest.ini).
No environment variable juggling needed here.
"""

import pytest


@pytest.fixture
def rf():
    from django.test import RequestFactory

    return RequestFactory()
