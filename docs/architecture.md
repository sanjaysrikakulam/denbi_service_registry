---
icon: material/sitemap
---

# Architecture

## System overview

```
                    Internet
                       │
                    [Nginx]               ← host reverse proxy (Ansible-managed)
                       │ HTTPS
                  [Gunicorn]              ← WSGI server (Docker container)
                       │
              [Django Application]
              ┌────────┴────────┐
         [WhiteNoise]      [DRF API]
         (static files)   (REST endpoints)
                       │
          ┌────────────┼────────────┐
     [PostgreSQL]   [Redis]    [Celery]
     (submissions,  (cache,    (async tasks:
      EDAM, bio.    sessions,   email dispatch,
      tools cache)  rate limit) bio.tools sync,
                               EDAM sync,
                               stale draft cleanup)
```

Traffic enters the host nginx, which terminates TLS and proxies to Gunicorn on `192.168.232.66:8000`. Gunicorn serves both the Django web application and the REST API. Static files are served directly through Gunicorn via WhiteNoise — no separate static file server.

---

## Django app structure

The project follows Django's app-per-domain convention. Each app has a single clear responsibility.

| App | Responsibility |
|---|---|
| `submissions` | Core domain. The `ServiceSubmission` model, registration form, views, and admin. |
| `api` | REST API layer. DRF viewsets, serializers, API key authentication, permissions. |
| `registry` | Reference data. `PrincipalInvestigator`, `ServiceCategory`, `ServiceCenter` models. |
| `biotools` | bio.tools integration. HTTP client, sync logic, Celery tasks, post_save signal. |
| `edam` | EDAM ontology. `EdamTerm` model, `sync_edam` management command. |

---

## Data model overview

```
ServiceSubmission (one per registered service)
├── SubmissionAPIKey (one-to-many — for scoped access)
├── BioToolsRecord (one-to-one — mirrored from bio.tools)
│   └── BioToolsFunction (one-to-many — EDAM function blocks)
├── PrincipalInvestigator (many-to-many — responsible and associated PIs)
├── ServiceCenter (many-to-many)
└── ServiceCategory (many-to-many)

EdamTerm (EDAM ontology cache — seeded via sync_edam)
└── parent → EdamTerm (self-referential, hierarchy)
```

`ServiceSubmission` references EDAM terms by URI strings (`edam_topics`, `edam_operations`) rather than foreign keys, so the submission model is not hard-coupled to the EDAM sync state.

---

## Request flow

### Web registration form

```
Browser → POST /register/
  → SubmissionForm.is_valid()
  → ServiceSubmission.objects.create()
  → post_save signal fires
  → sync_biotools_record.apply_async()  (if biotools_url set)
  → send_submission_notification.delay()
  → redirect → /register/success/
```

### REST API — create submission

```
Client → POST /api/v1/submissions/
  → ApiKeyAuthentication (no key required for create)
  → SubmissionSerializer.is_valid()
  → ServiceSubmission.objects.create()
  → SubmissionAPIKey.objects.create()  (one-time plaintext returned)
  → 201 Created { submission, api_key }
```

### REST API — read/update submission

```
Client → GET/PATCH /api/v1/submissions/{id}/
  → ApiKeyAuthentication  → validates HMAC hash
  → IsSubmissionOwner permission → checks key.submission == instance
  → SubmissionSerializer → excludes sensitive fields
  → 200 OK
```

---

## Async task processing

Celery workers connect to Redis and process three categories of tasks:

| Queue | Tasks | Schedule |
|---|---|---|
| Default | `send_submission_notification` — admin email on create/update/status change; submitter email on status change | On demand |
| Default | bio.tools record sync | On demand (post_save signal) |
| Beat (periodic) | `sync_all_biotools_records` — refresh all bio.tools records | Daily |
| Beat (periodic) | `edam.sync` — refresh EDAM ontology terms | Monthly (30 days) |
| Beat (periodic) | `cleanup_stale_drafts` — purge old incomplete submissions | Every 6 hours |

Celery beat runs in its own container alongside the worker container. The worker container's Docker healthcheck uses `celery inspect ping` via the Redis broker; beat has no inspection API so its healthcheck is disabled.

**Email flow on status change:** two separate emails are sent — one to the admin (full internal report) and one to `internal_contact_email` (plain-language submitter notification with status-specific messaging). The submitter email is suppressed when `SUBMISSION_NOTIFY_OVERRIDE` is set.

---

## Security design

| Control | Implementation |
|---|---|
| CSRF protection | Django's built-in CSRF middleware — all POST form views protected |
| API authentication | HMAC-based API key: plaintext hashed with PBKDF2, stored as `key_hash` |
| Admin authentication | Django auth + django-axes (brute-force lockout) |
| Content Security Policy | `django-csp` middleware — all third-party JS/CSS vendored locally; `script-src 'unsafe-inline'` retained for Django template inline scripts |
| Rate limiting | `django-ratelimit` on form submit and API create endpoints |
| Input sanitisation | `bleach` on all free-text fields in `ServiceSubmission.save()` |
| Sensitive field isolation | IP, user-agent hash, internal contact excluded from all API serializers |
| Logging scrubber | `ScrubSensitiveFilter` redacts `Authorization` and `Cookie` headers from logs |
| HSTS | Set in host nginx config (`max-age=31536000; includeSubDomains; preload`) |
| TLS | TLSv1.2+ only; OCSP stapling enabled in nginx |
| Admin URL | Configurable prefix via `ADMIN_URL_PREFIX` env var (default: `admin-denbi`) |

---

## Configuration layers

```
config/site.toml   ← non-secret, human-editable (name, URLs, features)
      ↓
.env               ← secrets (passwords, keys, SMTP credentials)
      ↓
config/settings.py ← Django settings (merges both, adds defaults)
      ↓
config/settings_test.py ← test overrides (SQLite, no Redis, no throttle)
```

All `site.toml` values are injected into every template via the `site_context` context processor.

---

## Static files

All static assets are vendored locally in `static/` — zero CDN requests at runtime (GDPR requirement):

| File | Version | Used by |
|---|---|---|
| `static/css/bootstrap.min.css` | Bootstrap 5.3.3 | All pages |
| `static/js/bootstrap.bundle.min.js` | Bootstrap 5.3.3 | All pages |
| `static/js/htmx.min.js` | HTMX 1.9.12 | bio.tools prefill |
| `static/css/tom-select.bootstrap5.min.css` | Tom-Select 2.3.1 | EDAM multi-select |
| `static/js/tom-select.complete.min.js` | Tom-Select 2.3.1 | EDAM multi-select |
| `static/swagger-ui/swagger-ui.css` | swagger-ui-dist 5.18.2 | `/api/docs/` |
| `static/swagger-ui/swagger-ui-bundle.js` | swagger-ui-dist 5.18.2 | `/api/docs/` |
| `static/swagger-ui/swagger-ui-standalone-preset.js` | swagger-ui-dist 5.18.2 | `/api/docs/` |
| `static/swagger-ui/favicon-32x32.png` | swagger-ui-dist 5.18.2 | `/api/docs/` |
| `static/redoc/bundles/redoc.standalone.js` | ReDoc 2.2.0 | `/api/redoc/` |
| `static/img/favicon.ico` | de.NBI favicon | All pages |
| `static/css/registry.css` | Project custom | All pages |

WhiteNoise serves these through Gunicorn with long `Cache-Control: public, immutable` headers.

When updating a vendored library, replace the file(s) in `static/` and update the version comment in `config/settings.py` (`SPECTACULAR_SETTINGS`) or the relevant widget `Media` class.
