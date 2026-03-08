# Configuration Reference

This document describes every configuration option for the de.NBI Service Registry.
Configuration is split into two files with a clear separation of concerns:

| File | What goes here | Restart needed? |
|---|---|---|
| `config/site.toml` | Branding, contact info, URLs, feature flags | Yes (`docker compose restart web worker beat`) |
| `.env` | Secrets, passwords, connection strings | Yes (full restart) |

---

## `config/site.toml` — Site settings

The single place for all non-secret, human-editable settings. Editing this file
and restarting the containers is all that is needed to rebrand the registry for
a different organisation.

### `[site]` — Core identity

```toml
[site]
name        = "de.NBI Service Registry"
tagline     = "de.NBI & ELIXIR-DE Service Registration System"
url         = "https://registry.denbi.de"
logo_url    = "https://www.denbi.de/templates/nbimaster/img/denbi-logo-color.svg"
form_version = "1.1"
form_date    = "2026-02-14"
```

| Key | Description |
|---|---|
| `name` | Site name shown in the navbar, page titles, and email subjects |
| `tagline` | Browser tab subtitle and meta description |
| `url` | Canonical public URL — used in outbound emails and the bio.tools API User-Agent |
| `logo_url` | Logo image URL. Empty string shows the CSS text fallback. A local static file can be referenced as `/static/img/logo.svg` after running `make collectstatic` |
| `form_version` / `form_date` | Shown in the registration form header |

### `[contact]` — Contact details

```toml
[contact]
email        = "servicecoordination@denbi.de"
office       = "Forschungszentrum Jülich GmbH - IBG-5, c/o Bielefeld University"
organisation = "German Network for Bioinformatics Infrastructure"
```

`contact.email` appears in:
- The registration form sidebar
- The update / lookup form
- The success page after submission
- All outbound email footers
- The OpenAPI contact metadata
- The site footer

### `[email]` — Sender identity

```toml
[email]
from_address   = "no-reply@denbi.de"
subject_prefix = "[de.NBI Registry]"
```

> **Note:** `from_address` is overridden by the `EMAIL_FROM` environment variable if that is set.
> SMTP credentials (host, port, password) stay in `.env`.

### `[links]` — External URLs

```toml
[links]
website         = "https://www.denbi.de"
privacy_policy  = "https://www.denbi.de/privacy-policy"
imprint         = "https://www.denbi.de/imprint"
data_protection = "https://www.denbi.de/?view=article&id=1968:services-dpi&catid=21"
kpi_cheatsheet  = "https://www.denbi.de/images/Service/20210624_KPI_Cheat_Sheet_doi.pdf"
```

All links are rendered dynamically — changing a URL here updates it everywhere
in the UI without touching template files.

### `[api]` — OpenAPI metadata

```toml
[api]
title        = "de.NBI Service Registry API"
version      = "1.0.0"
license_name = "MIT"
```

### `[features]` — Feature flags

```toml
[features]
biotools_prefill  = true   # Show bio.tools prefill banner on the form
edam_annotations  = true   # Show EDAM ontology fields on the form
captcha_enabled   = false  # Require hCaptcha/Turnstile (needs sitekey in .env)
```

---

## `.env` — Secrets and connection strings

Copy `.env.example` to `.env` and fill in the required values.

### Required (startup fails without these)

```bash
SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DB_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
```

### Database

```bash
DB_NAME=denbi_registry
DB_USER=denbi
DB_HOST=db          # Docker Compose service name
DB_PORT=5432
```

### Redis

```bash
REDIS_HOST=redis
REDIS_PORT=6379
```

### Django

```bash
DEBUG=false
ALLOWED_HOSTS=registry.denbi.de,www.registry.denbi.de
```

### Email (SMTP credentials)

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.org
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
# Overrides [email] from_address in site.toml if set:
EMAIL_FROM=no-reply@denbi.de
```

### CAPTCHA (optional)

```bash
HCAPTCHA_SITEKEY=
HCAPTCHA_SECRET_KEY=
# or Cloudflare Turnstile:
TURNSTILE_SITEKEY=
TURNSTILE_SECRET_KEY=
```

### EDAM ontology

```bash
# Default: latest stable OWL release.
# Pin a specific version:
EDAM_OWL_URL=https://edamontology.org/EDAM_1.25.owl
# Or a local file for air-gapped servers:
EDAM_OWL_URL=/app/EDAM.owl
```

### Optional

```bash
SENTRY_DSN=              # Error tracking
ADMIN_URL_PREFIX=admin   # Obscure the Django admin URL
```

---

## Using site.toml values in custom templates

All values from `site.toml` are injected into every Django template via the
`site_context` context processor. They are available as:

```django
{# Top-level shortcuts #}
{{ SITE_NAME }}
{{ SITE_URL }}
{{ CONTACT_EMAIL }}
{{ CONTACT_OFFICE }}
{{ CONTACT_ORG }}
{{ PRIVACY_POLICY_URL }}
{{ IMPRINT_URL }}
{{ WEBSITE_URL }}
{{ LOGO_URL }}

{# Full SITE dict — mirrors site.toml sections #}
{{ SITE.form_version }}
{{ SITE.contact.email }}
{{ SITE.links.kpi_cheatsheet }}
{{ SITE.features.biotools_prefill }}
{{ SITE.email.subject_prefix }}
```

---

## Deploying for a different organisation

To white-label this registry for another institution, only `config/site.toml`
needs to be edited:

1. Update `[site]`, `[contact]`, and `[links]` sections
2. Place your logo at `static/img/logo.svg` and set `logo_url = "/static/img/logo.svg"`
3. Run `docker compose exec web python manage.py collectstatic --noinput`
4. Restart: `docker compose restart web worker beat`

No Python, no template edits, no rebuild required.
