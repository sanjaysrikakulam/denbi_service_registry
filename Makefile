# =============================================================================
# de.NBI Service Registry — Developer Makefile
# =============================================================================
# Run `make` or `make help` to see available targets.
# =============================================================================

.PHONY: help build dev dev-down logs migrate superuser shell \
        test test-cov test-docker lint lint-fix lint-docker \
        audit audit-docker typecheck collectstatic \
        docs docs-build prod-up prod-down prod-migrate prod-logs clean

# --- Default -----------------------------------------------------------------

help:
	@echo ""
	@echo "de.NBI Service Registry — make targets"
	@echo ""
	@echo "  Development"
	@echo "    make dev              Start full dev stack (web + worker + beat + db + redis)"
	@echo "    make dev-down         Stop dev stack"
	@echo "    make build            Build / rebuild Docker images"
	@echo "    make logs             Tail dev stack logs"
	@echo "    make migrate          Run migrations in running web container"
	@echo "    make superuser        Create a Django superuser"
	@echo "    make shell            Open Django shell_plus"
	@echo "    make collectstatic    Collect static files"
	@echo ""
	@echo "  Testing  (no Docker, no external services required)"
	@echo "    make test             Run pytest with SQLite in-memory"
	@echo "    make test-cov         Run pytest + HTML coverage report"
	@echo ""
	@echo "  Testing  (via Docker)"
	@echo "    make test-docker      Run tests in Docker (SQLite, no db service)"
	@echo "    make lint-docker      ruff check + format check in Docker"
	@echo "    make audit-docker     pip-audit in Docker"
	@echo ""
	@echo "  Code quality  (requires: pip install -r requirements/development.txt)"
	@echo "    make lint             ruff check + format check"
	@echo "    make lint-fix         ruff autofix + format"
	@echo "    make audit            pip-audit against production requirements"
	@echo "    make typecheck        mypy type check"
	@echo ""
	@echo "  Documentation"
	@echo "    make docs             Serve MkDocs at http://127.0.0.1:8001"
	@echo "    make docs-build       Build static site into site/"
	@echo ""
	@echo "  Production"
	@echo "    make prod-up          Start production stack"
	@echo "    make prod-down        Stop production stack"
	@echo "    make prod-migrate     Run migrations in production web container"
	@echo "    make prod-logs        Tail production logs"
	@echo ""
	@echo "  Cleanup"
	@echo "    make clean            Remove containers + volumes (WARNING: deletes data)"
	@echo ""

# --- Development -------------------------------------------------------------

dev:
	docker compose up -d
	@echo "Dev stack running → http://localhost:8000"
	@echo "Run 'make migrate' on a fresh database."

dev-down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

migrate:
	docker compose exec web python manage.py migrate

superuser:
	docker compose exec web python manage.py createsuperuser

shell:
	docker compose exec web python manage.py shell_plus

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

# --- Testing (local — no Docker, no PostgreSQL, no Redis) --------------------

test:
	pytest tests/

test-cov:
	pytest tests/ --cov=apps --cov-report=term-missing --cov-report=html
	@echo "Open htmlcov/index.html to view coverage report."

# --- Testing (via Docker) ----------------------------------------------------

test-docker:
	docker compose -f docker/docker-compose.ci.yml run --rm test

lint-docker:
	docker compose -f docker/docker-compose.ci.yml run --rm lint

audit-docker:
	docker compose -f docker/docker-compose.ci.yml run --rm audit

# --- Code quality (local) ----------------------------------------------------

lint:
	ruff check apps/ config/ tests/
	ruff format --check apps/ config/ tests/

lint-fix:
	ruff check --fix apps/ config/ tests/
	ruff format apps/ config/ tests/

audit:
	pip-audit -r requirements/production.txt

typecheck:
	mypy apps/ config/

# --- Documentation -----------------------------------------------------------

docs:
	mkdocs serve --dev-addr 127.0.0.1:8001

docs-build:
	mkdocs build --strict

# --- Production --------------------------------------------------------------

prod-up:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

prod-migrate:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py migrate

prod-logs:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# --- Cleanup -----------------------------------------------------------------

clean:
	@echo "WARNING: deletes all containers and volumes including database data."
	@read -p "Are you sure? [y/N] " c && [ "$$c" = "y" ]
	docker compose down -v
