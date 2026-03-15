---
icon: material/rocket-launch
---

# Deployment Guide

> **Configuration:** see [Configuration Reference](configuration.md) for all settings including branding, contact email, and feature flags. — de.NBI Service Registry

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- A hostname with DNS pointing to your server (e.g. `service-registry.bi.denbi.de`)
- TLS certificate (Let's Encrypt recommended)
- Access to an SMTP server for email notifications

---

## Configuration

All configuration is via environment variables. There are no TOML config files to edit.

Copy `.env.example` to `.env` and fill in the three required values:

```bash
cp .env.example .env
```

**Required — startup fails without these:**

| Variable         | Description                                                                                                                                    |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `SECRET_KEY`     | Django secret key — generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DB_PASSWORD`    | PostgreSQL password — must match `POSTGRES_PASSWORD` used to initialise the DB volume                                                          |
| `REDIS_PASSWORD` | Redis password                                                                                                                                 |

Everything else has sensible defaults for development. See `.env.example` for the full reference.

---

## Quick Start (Development)

```bash
# 1. Clone the repository
git clone https://github.com/denbi/service-registry.git
cd service-registry

# 2. Configure environment
cp .env.example .env
# Edit .env — set SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD

# 3. Build and start services
make build
make up

# 4. Run database migrations
make migrate

# 5. Seed EDAM ontology terms (required for EDAM dropdowns in the form)
docker compose exec web python manage.py sync_edam

# 6. Create the first admin user
make superuser

# 7. Visit http://localhost:8000
```

---

## Production Deployment

### Step 1 — Configure environment

On the production server, create `.env` with production values:

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
SECRET_KEY=<generate-a-long-random-key>
DB_PASSWORD=<strong-random-password>
REDIS_PASSWORD=<strong-random-password>

DEBUG=false
ALLOWED_HOSTS=service-registry.bi.denbi.de

EMAIL_HOST=smtp.your-provider.org
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_FROM=no-reply@denbi.de

ADMIN_URL_PREFIX=your-secret-admin-path
```

### Step 2 — TLS certificates

Place certificates at `nginx/ssl/fullchain.pem` and `nginx/ssl/privkey.pem`.

**Using Let's Encrypt (certbot):**

```bash
apt install certbot
certbot certonly --standalone -d service-registry.bi.denbi.de
cp /etc/letsencrypt/live/service-registry.bi.denbi.de/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/service-registry.bi.denbi.de/privkey.pem nginx/ssl/
```

Set up automatic renewal:

```bash
certbot renew --pre-hook "docker compose stop nginx" --post-hook "docker compose start nginx"
```

### Step 3 — Update Nginx config

Edit `nginx/nginx.conf` — update `server_name` to your hostname:

```nginx
server_name service-registry.bi.denbi.de;
```

### Step 4 — Start production services

```bash
make prod-up
make prod-migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py createsuperuser
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py sync_edam
```

### Step 5 — Collect static files

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

---

## Migrations

Always run migrations before restarting after an update:

```bash
make prod-migrate
```

Migrations are tracked in version control under `apps/*/migrations/`. Never edit generated migration files manually.

---

## Initial Data (Fixtures)

Seed the PI list and service centres:

```bash
docker compose exec web python manage.py loaddata apps/registry/fixtures/initial_pis.json
docker compose exec web python manage.py loaddata apps/registry/fixtures/initial_centres.json
```

(Fixture files to be created separately with the full de.NBI PI list.)

---

## EDAM Ontology Seeding

The EDAM ontology (~3,400 terms) powers the Topic and Operation dropdowns on the
registration form. The application handles seeding in three ways — no manual step
is required on a standard first deployment.

### Automatic seeding on first migrate

When `manage.py migrate` runs against a **fresh database** (empty `EdamTerm` table),
it automatically downloads and imports EDAM from `EDAM_OWL_URL`. This happens as
a `post_migrate` signal — you will see progress output at the end of `migrate`:

```
[edam] EdamTerm table is empty — running initial EDAM sync.
[edam] This downloads ~3 MB from edamontology.org and may take ~30 seconds.
[edam] Loading EDAM from: https://edamontology.org/EDAM_stable.owl
...
[edam] Auto-seed complete — 3471 terms loaded (EDAM 1.25).
```

On subsequent `migrate` runs (e.g. applying a new migration), the table is not
empty so the signal is a no-op.

### Ongoing automatic updates

Celery beat runs a full EDAM sync **every 30 days** automatically. EDAM releases
are infrequent (~1–2 per year) so monthly is more than sufficient.

### Manual sync

Force a sync at any time via:

- **Admin UI**: Go to **EDAM Ontology → EDAM Terms** and click **↻ Sync EDAM from upstream**.
  The sync runs as a background Celery task; refresh the page after ~30 seconds.

- **CLI**:
  ```bash
  docker compose exec web python manage.py sync_edam
  ```

Verify the current state:

```bash
docker compose exec web python manage.py shell -c \
  "from apps.edam.models import EdamTerm; t = EdamTerm.objects.first(); print(EdamTerm.objects.count(), 'terms, version', t.edam_version)"
```

### Air-gapped / firewall-restricted servers

If the server cannot reach edamontology.org, download the OWL file on another machine
and copy it across:

```bash
# On a machine with internet access:
curl -o EDAM.owl https://edamontology.org/EDAM_stable.owl
# Copy EDAM.owl to the server, then:
```

Either set the path permanently in `.env`:

```bash
EDAM_OWL_URL=/app/EDAM.owl
```

Or pass it once to the management command:

```bash
docker compose exec web python manage.py sync_edam --url /app/EDAM.owl
```

The auto-seed on first migrate also respects `EDAM_OWL_URL`, so an air-gapped
deployment works without any code changes.

---

## Network Requirements

| Destination        | Port | When needed                       | Purpose                |
| ------------------ | ---- | --------------------------------- | ---------------------- |
| `bio.tools`        | 443  | On form submission + daily        | bio.tools API sync     |
| `edamontology.org` | 443  | Manual `sync_edam` runs only      | EDAM ontology download |
| Your SMTP server   | 587  | On every submission/status change | Email notifications    |

---

## Updating the Application

```bash
git pull origin main
docker compose build
make prod-migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-deps web worker beat
```

---

## Logo

To display your organisation logo in the navbar:

1. Place your logo file at `static/img/logo.png` (or `.svg`, `.jpg`)
2. Rebuild static files: `make collectstatic`

Or set `LOGO_URL` in `.env` to point to any image URL:

```bash
# Local static file (after collectstatic)
LOGO_URL=/static/img/logo.png

# External URL
LOGO_URL=https://www.denbi.de/images/logos/denbi-logo.png
```

Recommended logo height is 38px. The image renders in the top-left of the navbar
alongside the site name text.

---

## Backup

### Database

```bash
# Backup
docker compose exec db pg_dump -U denbi denbi_registry > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U denbi denbi_registry < backup_20260306.sql
```

### Redis

Redis holds only transient Celery queue data and does not need persistent backup.

---

## Security Checklist (pre-launch)

- [ ] `DEBUG=false` in `.env`
- [ ] `SECRET_KEY` is unique and at least 50 characters
- [ ] Strong passwords for `DB_PASSWORD` and `REDIS_PASSWORD`
- [ ] TLS certificate installed and auto-renewal configured
- [ ] HSTS preload submitted to [hstspreload.org](https://hstspreload.org)
- [ ] `ADMIN_URL_PREFIX` changed from default `admin-denbi`
- [ ] `ALLOWED_HOSTS` set to production hostname only
- [ ] All containers running as non-root (`docker compose ps` → verify USER column)
- [ ] `pip-audit` passes: `make audit`
- [ ] Health checks passing: `curl https://service-registry.bi.denbi.de/health/ready/`
- [ ] Test email notification by submitting a test form

---

## Troubleshooting

**Web service not starting:**

```bash
docker compose logs web
# Common causes: missing SECRET_KEY, DB_PASSWORD, or REDIS_PASSWORD in .env
# The startup error will name the missing variable explicitly
```

**Database authentication failure:**

```bash
# Verify what password Django is using
docker compose exec web python -c "
from django.conf import settings
d = settings.DATABASES['default'].copy()
d['PASSWORD'] = '***'
print(d)
"
# Make sure DB_PASSWORD in .env matches the password the DB volume was initialised with
# If unsure, wipe the volume and start fresh:
#   make clean && make up
```

**Emails not sending:**

```bash
docker compose logs worker
docker compose exec worker python -c \
  "from django.core.mail import send_mail; send_mail('test','test','from@example.com',['to@example.com'])"
```

**Rate limit 429 errors in testing:**

```bash
# Increase limits in .env:
RATE_LIMIT_SUBMIT=1000/h
RATE_LIMIT_UPDATE=1000/h
```

**EDAM dropdowns empty:**

```bash
docker compose exec web python manage.py sync_edam
```
