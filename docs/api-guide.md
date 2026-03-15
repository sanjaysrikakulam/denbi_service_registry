---
icon: material/api
---

# API Guide

The de.NBI Service Registry REST API allows programmatic access to service registrations.

Interactive documentation is available at:

- **Swagger UI**: `/api/docs/`
- **ReDoc**: `/api/redoc/`
- **OpenAPI schema** (JSON): `/api/schema/`

Both Swagger UI (swagger-ui-dist 5.18.2) and ReDoc (2.2.0) assets are vendored locally in `static/` — no CDN or external requests are made when loading the docs pages.

---

## Authentication

Two authentication schemes are supported.

### Admin Token (`Authorization: Token <key>`)

For staff users and trusted integrations. Grants access to the full submission list
and all reference data endpoints.

**Creating a token:**

1. Log in to `/admin-denbi/`
2. Go to **Auth Token → Tokens → Add Token**
3. Select the staff user and save
4. Copy the key — it is shown in full on the token detail page

**Using it:**

```bash
curl https://service-registry.bi.denbi.de/api/v1/submissions/ \
  -H "Authorization: Token d876555a570df89909058eeeb6d88f4b814a81a1"
```

### Submission API Key (`Authorization: ApiKey <key>`)

Issued when a service is registered (via the web form or `POST /api/v1/submissions/`).
Scoped to a single submission. The plaintext key is shown **once** — store it securely.

Two scopes are available (set by admins via the API Key admin):

| Scope   | Allowed methods |
| ------- | --------------- |
| `read`  | GET only        |
| `write` | GET + PATCH     |

**Using it:**

```bash
curl https://service-registry.bi.denbi.de/api/v1/submissions/<id>/ \
  -H "Authorization: ApiKey <your-key>"
```

---

## Endpoints

### `POST /api/v1/submissions/` — Register a service

No authentication required. Submits a new service registration.

**Response (201):**

```json
{
  "id": "26a59fcb-...",
  "service_name": "MyTool",
  "api_key": "oGzQk9...",
  "api_key_warning": "This key is shown ONCE. Store it securely.",
  "status": "submitted",
  ...
}
```

---

### `GET /api/v1/submissions/` — List all submissions

Requires admin Token. Returns paginated full detail for all submissions.

**Query parameters:**

| Parameter            | Example                       | Description                      |
| -------------------- | ----------------------------- | -------------------------------- |
| `status`             | `?status=approved`            | Filter by status                 |
| `service_center`     | `?service_center=BioinfoProt` | Filter by centre short name      |
| `year_established`   | `?year_established=2021`      | Filter by year                   |
| `register_as_elixir` | `?register_as_elixir=true`    | Filter by ELIXIR flag            |
| `ordering`           | `?ordering=-submitted_at`     | Sort (prefix `-` for descending) |

**Response (200):**

```json
{
  "count": 42,
  "next": "http://.../api/v1/submissions/?page=2",
  "previous": null,
  "results": [
    {
      "id": "...",
      "service_name": "...",
      "status": "approved",
      "edam_topics": [{"uri": "...", "accession": "topic_0091", "label": "Proteomics"}],
      "edam_operations": [...],
      "responsible_pis": [{"last_name": "...", "orcid": "..."}],
      "biotoolsrecord": { ... },
      ...
    }
  ]
}
```

---

### `GET /api/v1/submissions/{id}/` — Retrieve your submission

Requires `ApiKey`. Returns your own submission in full detail.
Returns 403 if the key does not belong to this submission.

---

### `PATCH /api/v1/submissions/{id}/` — Update your submission

Requires `ApiKey` with `write` scope. Partial update — include only changed fields.

Updating an approved submission resets its status to `submitted` for re-review.

```bash
curl -X PATCH https://service-registry.bi.denbi.de/api/v1/submissions/<id>/ \
  -H "Authorization: ApiKey <your-key>" \
  -H "Content-Type: application/json" \
  -d '{"kpi_start_year": "2026"}'
```

Full `PUT` is not supported — use `PATCH`.

---

### `GET /api/v1/categories/` — Service categories

Admin Token required. Returns all active service categories.

### `GET /api/v1/service-centers/` — Service centres

Admin Token required. Returns all active de.NBI service centres.

### `GET /api/v1/pis/` — Principal investigators

Admin Token required. Returns all active PIs.

### `GET /api/v1/edam/` — EDAM ontology terms

**Public** — no authentication required. Returns all non-obsolete EDAM terms.

Filter: `?branch=topic|operation|data|format`, `?q=<search>`

### `GET /api/v1/edam/{accession}/` — EDAM term detail

Public. Look up by accession (e.g. `topic_0091`) or UUID.

---

## Response shape

All error responses follow this envelope:

```json
{
  "error": { "detail": "Authentication credentials were not provided." },
  "request_id": "8e26f6d5-0094-48ea-9a36-c417921815a9"
}
```

The `request_id` is included in every response (success and error) as `X-Request-ID`
header and in error bodies. Use it when reporting issues.

---

## Excluded fields

The following fields are **never** included in any API response regardless of authentication level:

- `internal_contact_email`
- `internal_contact_name`
- `submission_ip`
- `user_agent_hash`

---

## curl examples

```bash
# Register a new service (public)
curl -X POST https://service-registry.bi.denbi.de/api/v1/submissions/ \
  -H "Content-Type: application/json" \
  -d @submission.json

# List all submissions (admin token)
curl https://service-registry.bi.denbi.de/api/v1/submissions/ \
  -H "Authorization: Token <admin-token>"

# Retrieve your submission (ApiKey)
curl https://service-registry.bi.denbi.de/api/v1/submissions/<id>/ \
  -H "Authorization: ApiKey <your-key>"

# Update a field (ApiKey, write scope)
curl -X PATCH https://service-registry.bi.denbi.de/api/v1/submissions/<id>/ \
  -H "Authorization: ApiKey <your-key>" \
  -H "Content-Type: application/json" \
  -d '{"website_url": "https://new-url.example.com"}'

# Browse EDAM topics (public)
curl "https://service-registry.bi.denbi.de/api/v1/edam/?branch=topic&q=proteomics"
```
