# Deployment Guide

> **Configuration:** see [Configuration Reference](configuration.md) for all settings including branding, contact email, and feature flags. — de.NBI Service Registry

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- A hostname with DNS pointing to your server (e.g. `registry.denbi.de`)
- TLS certificate (Let's Encrypt recommended)
- Access to an SMTP server for email notifications
- (Optional) A CAPTCHA provider account (hCaptcha or Cloudflare Turnstile)

---

## Configuration

All configuration is via environment variables. There are no TOML config files to edit.

Copy `.env.example` to `.env` and fill in the three required values:

```bash
cp .env.example .env
```

**Required — startup fails without these:**

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key — generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DB_PASSWORD` | PostgreSQL password — must match `POSTGRES_PASSWORD` used to initialise the DB volume |
| `REDIS_PASSWORD` | Redis password |

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
ALLOWED_HOSTS=registry.denbi.de

EMAIL_HOST=smtp.your-provider.org
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_FROM=no-reply@denbi.de

CAPTCHA_ENABLED=true
HCAPTCHA_SECRET_KEY=your-hcaptcha-secret
HCAPTCHA_SITEKEY=your-hcaptcha-sitekey

ADMIN_URL_PREFIX=your-secret-admin-path
```

### Step 2 — TLS certificates

Place certificates at `nginx/ssl/fullchain.pem` and `nginx/ssl/privkey.pem`.

**Using Let's Encrypt (certbot):**
```bash
apt install certbot
certbot certonly --standalone -d registry.denbi.de
cp /etc/letsencrypt/live/registry.denbi.de/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/registry.denbi.de/privkey.pem nginx/ssl/
```

Set up automatic renewal:
```bash
certbot renew --pre-hook "docker compose stop nginx" --post-hook "docker compose start nginx"
```

### Step 3 — Update Nginx config

Edit `nginx/nginx.conf` — update `server_name` to your hostname:
```nginx
server_name registry.denbi.de;
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

**This step is required before the registration form can offer EDAM term selection.**
Without it, the EDAM Topic and EDAM Operations dropdowns will be empty.

Run once after the first deployment and again when a new EDAM release is published:

```bash
# Downloads terms from EDAM_OWL_URL (default: EDAM_stable.owl, ~30 seconds)
docker compose exec web python manage.py sync_edam
```

Verify it succeeded:
```bash
docker compose exec web python manage.py shell -c \
  "from apps.edam.models import EdamTerm; print(f'Loaded {EdamTerm.objects.count()} EDAM terms')"
# Expected: Loaded 4165 EDAM terms (number varies by release)
```

If your server cannot reach edamontology.org (firewall), download the JSON on another machine:

```bash
# On a machine with internet access:
curl -o EDAM.owl https://edamontology.org/EDAM_stable.owl

# Copy to server and load from local path:
# Either set in .env:
#   EDAM_OWL_URL=/app/EDAM.owl
# Or pass directly:
docker compose exec web python manage.py sync_edam --url /app/EDAM.owl
```

---

## Network Requirements

| Destination | Port | When needed | Purpose |
|-------------|------|-------------|---------|
| `bio.tools` | 443 | On form submission + daily | bio.tools API sync |
| `edamontology.org` | 443 | Manual `sync_edam` runs only | EDAM ontology download |
| Your SMTP server | 587 | On every submission/status change | Email notifications |

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
- [ ] `CAPTCHA_ENABLED=true` and CAPTCHA keys configured
- [ ] `ADMIN_URL_PREFIX` changed from default `admin-denbi`
- [ ] `ALLOWED_HOSTS` set to production hostname only
- [ ] All containers running as non-root (`docker compose ps` → verify USER column)
- [ ] `pip-audit` passes: `make audit`
- [ ] Health checks passing: `curl https://registry.denbi.de/health/ready/`
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

**CAPTCHA failures in development:**
```bash
# CAPTCHA is disabled by default when DEBUG=true.
# To force-disable in production-like testing:
CAPTCHA_ENABLED=false
```

**EDAM dropdowns empty:**
```bash
docker compose exec web python manage.py sync_edam
```
