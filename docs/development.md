---
icon: material/code-braces
---

# Development Setup

## Prerequisites

- [Docker Engine](https://docs.docker.com/engine/install/) 24+
- [Conda / Miniforge](https://github.com/conda-forge/miniforge) (for local Python work without Docker)
- Git

---

## Option A: Docker Compose (recommended)

All services run in containers — nothing to install locally beyond Docker.

```bash
git clone https://github.com/deNBI/denbi_service_registry
cd denbi_service_registry

# 1. Copy and edit environment
cp .env.example .env
# Set at minimum: SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD

# 2. Start all services (web, worker, beat, db, redis)
docker compose up -d

# 3. Run migrations
docker compose exec web python manage.py migrate

# 4. Create superuser
docker compose exec web python manage.py createsuperuser

# 5. (Optional) Force EDAM ontology sync — happens automatically on first migrate
#    but you can re-run it manually any time
docker compose exec web python manage.py sync_edam
```

The app is at **http://localhost:8000** and the admin at **http://localhost:8000/admin-denbi/**.

> **EDAM auto-seed**: On the very first `migrate` against a fresh database, EDAM terms
> are downloaded and imported automatically (~30 s). The EDAM Topic and Operation
> dropdowns will be populated without any manual step.

---

## Option B: Conda environment

Useful for running tests, linting, or working on the Python code without Docker.

```bash
# Create environment
conda create -n denbi-registry python=3.12
conda activate denbi-registry
pip install -r requirements/base.txt -r requirements/development.txt

# Point Django at test settings (SQLite in-memory, no Redis needed)
export DJANGO_SETTINGS_MODULE=config.settings_test
```

The conda environment is named `denbi-registry` in this project.

---

## Make targets

All common tasks are in the `Makefile`. Run `make help` for the full list.

**Development**

| Target | What it does |
|---|---|
| `make dev` | Start full dev stack (web + worker + beat + db + redis) |
| `make dev-down` | Stop the dev stack |
| `make build` | Build / rebuild Docker images |
| `make logs` | Tail dev stack logs |
| `make migrate` | Run Django migrations in the `web` container |
| `make superuser` | Create a Django superuser |
| `make shell` | Open Django `shell_plus` in the `web` container |
| `make collectstatic` | Collect static files into the container's `/static/` directory |

**Testing**

| Target | What it does |
|---|---|
| `make test` | Run pytest with SQLite in-memory (no Docker, no external services) |
| `make test-cov` | Run tests and generate HTML coverage report (`htmlcov/`) |
| `make test-docker` | Run tests inside Docker (via `docker/docker-compose.ci.yml`) |
| `make lint-docker` | Run ruff inside Docker |
| `make audit-docker` | Run `pip-audit` inside Docker |

**Code quality** (requires `pip install -r requirements/development.txt`)

| Target | What it does |
|---|---|
| `make lint` | Run ruff check + format check |
| `make lint-fix` | Auto-fix ruff lint and formatting issues |
| `make audit` | `pip-audit` against production requirements |
| `make typecheck` | Run mypy type checker |

**Documentation**

| Target | What it does |
|---|---|
| `make docs` | Serve MkDocs locally at http://127.0.0.1:8001 |
| `make docs-build` | Build static MkDocs site into `site/` (`--strict`) |

**Production**

| Target | What it does |
|---|---|
| `make prod-up` | Start production stack (compose + prod overlay) |
| `make prod-down` | Stop production stack |
| `make prod-migrate` | Run migrations in the production web container |
| `make prod-logs` | Tail production logs |

**Cleanup**

| Target | What it does |
|---|---|
| `make clean` | Remove all containers and volumes — **deletes all data**, prompts for confirmation |

---

## Project layout

```
denbi_service_registry/
├── apps/
│   ├── api/          — DRF viewsets, serializers, authentication
│   ├── biotools/     — bio.tools HTTP client, sync, signal, Celery tasks
│   ├── edam/         — EDAM ontology model, sync management command
│   ├── registry/     — Reference data (PIs, categories, service centres)
│   └── submissions/  — Core model, registration form, views, admin
├── config/
│   ├── settings.py   — Main Django settings
│   ├── settings_test.py — Test overrides (SQLite, no Redis)
│   ├── celery.py     — Celery app definition
│   └── site.toml     — Non-secret site configuration
├── docker/           — Docker Compose overlays (prod, CI)
├── docs/             — MkDocs documentation source
├── nginx/host/       — Host nginx vhost configuration (Ansible-managed)
├── requirements/     — base.txt, production.txt, development.txt
├── static/           — Vendored static assets (Bootstrap, HTMX, Tom-Select, swagger-ui, redoc, favicon)
├── templates/        — Django HTML templates
└── tests/            — pytest test suite
```

---

## Running tests

```bash
# With conda environment active:
pytest tests/

# Or via make (uses conda env automatically if configured):
make test

# With HTML coverage report:
make test-cov
# then open htmlcov/index.html
```

Tests use SQLite in-memory and local-memory cache — no PostgreSQL or Redis required.

See [Testing](testing.md) for writing new tests.

---

## Code quality

```bash
# Check for linting issues
make lint

# Auto-fix
make lint-fix

# Type checking
make typecheck
```

The CI pipeline runs `lint` and `test` on every push. Both must pass before merging.

---

## Vendored static assets

All third-party CSS and JavaScript is downloaded once and committed to `static/`. No CDN is contacted at runtime. This is a hard requirement for GDPR compliance — browser requests to jsDelivr, Google Fonts, unpkg, or any other CDN would constitute data transfers to third parties without user consent.

### Current inventory

| Asset | Version | Location | Used by |
|---|---|---|---|
| Bootstrap | 5.3.3 | `static/css/bootstrap.min.css`, `static/js/bootstrap.bundle.min.js` | All pages |
| HTMX | 1.9.12 | `static/js/htmx.min.js` | bio.tools prefill |
| Tom-Select | 2.3.1 | `static/css/tom-select.bootstrap5.min.css`, `static/js/tom-select.complete.min.js` | EDAM multi-select widget |
| swagger-ui-dist | 5.18.2 | `static/swagger-ui/` (4 files) | `/api/docs/` |
| ReDoc | 2.2.0 | `static/redoc/bundles/redoc.standalone.js` | `/api/redoc/` |
| de.NBI favicon | — | `static/img/favicon.ico` | All pages, admin |

### Updating a library

**Bootstrap** (`static/css/bootstrap.min.css`, `static/js/bootstrap.bundle.min.js`)

```bash
VERSION=5.3.4
BASE=https://cdn.jsdelivr.net/npm/bootstrap@${VERSION}/dist
curl -sSfL ${BASE}/css/bootstrap.min.css -o static/css/bootstrap.min.css
curl -sSfL ${BASE}/js/bootstrap.bundle.min.js -o static/js/bootstrap.bundle.min.js
```

**HTMX** (`static/js/htmx.min.js`)

```bash
VERSION=1.9.13
curl -sSfL https://unpkg.com/htmx.org@${VERSION}/dist/htmx.min.js -o static/js/htmx.min.js
```

**Tom-Select** (`static/css/tom-select.bootstrap5.min.css`, `static/js/tom-select.complete.min.js`)

```bash
VERSION=2.4.1
BASE=https://cdn.jsdelivr.net/npm/tom-select@${VERSION}/dist
curl -sSfL ${BASE}/css/tom-select.bootstrap5.min.css -o static/css/tom-select.bootstrap5.min.css
curl -sSfL ${BASE}/js/tom-select.complete.min.js -o static/js/tom-select.complete.min.js
```

Tom-Select is loaded via Django's widget `Media` class in `apps/submissions/widgets.py` — no template change needed when upgrading.

**swagger-ui-dist** (`static/swagger-ui/`)

```bash
VERSION=5.18.3
BASE=https://cdn.jsdelivr.net/npm/swagger-ui-dist@${VERSION}
for f in swagger-ui.css swagger-ui-bundle.js swagger-ui-standalone-preset.js favicon-32x32.png; do
    curl -sSfL ${BASE}/${f} -o static/swagger-ui/${f}
done
```

Then update the version comment in `config/settings.py`:
```python
# swagger-ui-dist 5.18.3, redoc 2.2.0 — vendored in static/swagger-ui/ and static/redoc/
"SWAGGER_UI_DIST": "/static/swagger-ui",
```

**ReDoc** (`static/redoc/bundles/redoc.standalone.js`)

```bash
VERSION=2.2.0
curl -sSfL https://cdn.jsdelivr.net/npm/redoc@${VERSION}/bundles/redoc.standalone.js \
    -o static/redoc/bundles/redoc.standalone.js
```

### Can I use an external URL instead of vendoring?

It depends on the asset type:

| Asset type | External URL acceptable? | Notes |
|---|---|---|
| **Logo** (`logo_url` in `site.toml`) | Yes | The CSP `img-src` directive is built dynamically from this URL via `_csp_img_origins()` in `settings.py`. Set it to any `https://` URL and CSP updates automatically. |
| **Favicon** (`favicon_url` in `site.toml`) | Yes | Same dynamic CSP behaviour as logo. |
| **JS/CSS frameworks** (Bootstrap, HTMX, Tom-Select) | **No** | Would make external network requests from the user's browser, violating GDPR. Must be vendored. |
| **Swagger UI / ReDoc** | **No** | drf-spectacular's `SWAGGER_UI_DIST` setting defaults to jsDelivr. We override it to `/static/swagger-ui`. Do not revert to a CDN URL. |

### Checking for CDN leakage

Use browser DevTools → Network tab, filter by third-party requests. All requests should resolve to `localhost` (dev) or your own domain (prod). Alternatively, check the CSP report — any CDN request will violate `default-src 'self'` and show up in the browser console as a blocked request.

---

## Adding a feature

1. Create a branch: `git checkout -b feature/my-feature`
2. Make changes, add tests
3. `make lint-fix && make test` — ensure lint and coverage pass
4. Open a pull request against `main`
