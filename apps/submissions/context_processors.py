"""
Template context processors
============================
All values from config/site.toml are injected into every template as the
``SITE`` context variable.  Templates access them like:

    {{ SITE.contact.email }}
    {{ SITE.links.privacy_policy }}
    {{ SITE.name }}           {# shortcut for SITE.site.name #}
    {{ LOGO_URL }}            {# kept as a top-level shortcut #}

The full structure mirrors site.toml exactly, so adding a new key there
makes it immediately available in all templates without touching Python code.
"""
from pathlib import Path

from django.conf import settings as dj_settings
from django.templatetags.static import static


def site_context(request):
    """
    Inject the entire SITE_CONFIG dict plus convenience shortcuts into
    every template context.
    """
    sc: dict = getattr(dj_settings, "SITE_CONFIG", {})

    site   = sc.get("site",    {})
    cont   = sc.get("contact", {})
    links  = sc.get("links",   {})
    email  = sc.get("email",   {})
    feats  = sc.get("features",{})

    # ---------------------------------------------------------------------------
    # Logo URL resolution — same priority chain as before:
    #   1. site.toml [site] logo_url
    #   2. Static file auto-detection (static/img/logo.{png,svg,…})
    #   3. Empty string → CSS text fallback in base.html
    # ---------------------------------------------------------------------------
    logo_url = site.get("logo_url", "")
    if not logo_url:
        static_img = Path(dj_settings.BASE_DIR) / "static" / "img"
        for ext in ("svg", "png", "jpg", "jpeg", "webp"):
            if (static_img / f"logo.{ext}").exists():
                logo_url = static(f"img/logo.{ext}")
                break

    return {
        # Full config dict — {{ SITE.contact.email }}, {{ SITE.links.kpi_cheatsheet }}, …
        "SITE": {
            **site,
            "contact":  cont,
            "links":    links,
            "email":    email,
            "features": feats,
        },
        # Top-level shortcuts for the most-used values
        "LOGO_URL":          logo_url,
        "SITE_NAME":         site.get("name",    "de.NBI Service Registry"),
        "SITE_URL":          site.get("url",     ""),
        "CONTACT_EMAIL":     cont.get("email",   "servicecoordination@denbi.de"),
        "CONTACT_OFFICE":    cont.get("office",  ""),
        "CONTACT_ORG":       cont.get("organisation", "German Network for Bioinformatics Infrastructure"),
        "PRIVACY_POLICY_URL":links.get("privacy_policy", "https://www.denbi.de/privacy-policy"),
        "IMPRINT_URL":       links.get("imprint",        "https://www.denbi.de/imprint"),
        "WEBSITE_URL":       links.get("website",        "https://www.denbi.de"),
    }
