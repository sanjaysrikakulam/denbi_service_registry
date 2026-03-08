"""
Custom template tags for de.NBI Service Registry.
Provides access to site configuration values in templates that don't
receive the submissions context processor (e.g. admin templates).
"""
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def site_logo_url():
    """Return the logo URL from site.toml, or empty string."""
    return getattr(settings, "SITE_CONFIG", {}).get("site", {}).get("logo_url", "")


@register.simple_tag
def site_setting(section, key, default=""):
    """Generic accessor: {% site_setting 'site' 'name' %}"""
    return getattr(settings, "SITE_CONFIG", {}).get(section, {}).get(key, default)
