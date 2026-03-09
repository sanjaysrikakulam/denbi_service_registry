# de.NBI Service Registry

A Django-based web application for managing de.NBI & ELIXIR-DE service registrations.

## Quick Start

```bash
cp .env.example .env
# Edit .env — set SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD
make build && make up
make migrate
docker compose exec web python manage.py sync_edam   # seed EDAM ontology
make superuser
# Open http://localhost:8000
```

## Documentation

| Document                                                           | Audience   | Description                                          |
| ------------------------------------------------------------------ | ---------- | ---------------------------------------------------- |
| [docs/user-guide.md](docs/user-guide.md)                           | Submitters | How to submit and edit a service registration        |
| [docs/admin-guide.md](docs/admin-guide.md)                         | Admins     | Managing submissions, PIs, API keys, EDAM, bio.tools |
| [docs/api-guide.md](docs/api-guide.md)                             | Developers | REST API reference and examples                      |
| [docs/deployment.md](docs/deployment.md)                           | Operators  | Initial production deployment                        |
| [docs/rollout.md](docs/rollout.md)                                 | Operators  | Versioning, CI, release, rollback runbook            |
| [docs/extending/model-changes.md](docs/extending/model-changes.md) | Developers | Adding/changing database fields and migrations       |
| [docs/extending/adding-apps.md](docs/extending/adding-apps.md)     | Developers | Adding new apps, endpoints, features                 |

Interactive API docs: `/api/docs/` (Swagger UI) and `/api/redoc/` (ReDoc).

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and fill in:

| Variable         | Required | Description                                                |
| ---------------- | -------- | ---------------------------------------------------------- |
| `SECRET_KEY`     | ✓        | Django secret key                                          |
| `DB_PASSWORD`    | ✓        | PostgreSQL password                                        |
| `REDIS_PASSWORD` | ✓        | Redis password                                             |
| `DEBUG`          |          | `true` for dev, `false` for production (default: `false`)  |
| `ALLOWED_HOSTS`  |          | Comma-separated hostnames (default: `localhost,127.0.0.1`) |

See `.env.example` for the full variable reference.

## Architecture

```
Internet
  │
  ▼
Host Nginx (nginx/host/registry.denbi.de.conf)
  │  TLS termination, certbot, IP allowlist
  │
  ▼ :8080 (de.NBI service registry VM)
Django / Gunicorn (web)
  │
  ├─▶ PostgreSQL (db)
  └─▶ Redis (redis) ─▶ Celery Worker (worker)
                    ─▶ Celery Beat (beat)
```

## Docker Compose Files

| File                                | Purpose                                           |
| ----------------------------------- | ------------------------------------------------- |
| `docker-compose.yml`                | Development (runserver, live reload)              |
| `docker-compose.prod.yml`           | Production overlay (Gunicorn, Nginx on 127.0.0.1) |
| `docker/docker-compose.ci.yml`      | CI pipeline (tests, lint, audit)                  |
| `docker/docker-compose.staging.yml` | Staging overlay                                   |
| `docker/docker-compose.swarm.yml`   | Docker Swarm stack                                |
| `docker/docker-compose.backup.yml`  | Automated DB backup sidecar                       |

## Tests

```bash
make test
# Or directly:
pytest tests/ -v
pytest tests/test_api.py -v
pytest tests/test_security.py -v
```

## Technology Stack

Django 5 · Django REST Framework · drf-spectacular · HTMX · Bootstrap 5
· Celery + Redis · PostgreSQL · Nginx · factory_boy · pytest
