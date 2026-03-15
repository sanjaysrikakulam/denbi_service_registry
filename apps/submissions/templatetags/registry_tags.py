"""
Custom template tags for de.NBI Service Registry.
Provides access to site configuration values in templates that don't
receive the submissions context processor (e.g. admin templates).
"""

from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def site_logo_url():
    """Return the logo URL from site.toml, or empty string."""
    return getattr(settings, "SITE_CONFIG", {}).get("site", {}).get("logo_url", "")


@register.simple_tag
def site_favicon_url():
    """
    Return the favicon URL.
    Priority: site.toml [site] favicon_url → auto-detect static/img/favicon.* → empty string.
    """
    url = getattr(settings, "SITE_CONFIG", {}).get("site", {}).get("favicon_url", "")
    if url:
        return url
    static_img = Path(settings.BASE_DIR) / "static" / "img"
    for fname in ("favicon.ico", "favicon.png", "favicon.svg"):
        if (static_img / fname).exists():
            return static(f"img/{fname}")
    return ""


@register.simple_tag
def site_setting(section, key, default=""):
    """Generic accessor: {% site_setting 'site' 'name' %}"""
    return getattr(settings, "SITE_CONFIG", {}).get(section, {}).get(key, default)
