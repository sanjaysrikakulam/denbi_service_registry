# =============================================================================
# de.NBI Service Registry — Makefile
# =============================================================================
# Common development tasks. Run `make help` for a summary.
# =============================================================================

.PHONY: help build up down migrate superuser shell test lint audit logs \
        collectstatic worker beat clean

# Default target
help:
	@echo ""
	@echo "de.NBI Service Registry — Make targets"
	@echo "======================================="
	@echo "  make up           Start all services (development)"
	@echo "  make down         Stop all services"
	@echo "  make build        Build / rebuild Docker images"
	@echo "  make migrate      Run database migrations"
	@echo "  make superuser    Create a Django superuser"
	@echo "  make shell        Open Django shell_plus"
	@echo "  make test         Run pytest test suite"
	@echo "  make lint         Run ruff linter"
	@echo "  make audit        Run pip-audit for security vulnerabilities"
	@echo "  make logs         Tail all service logs"
	@echo "  make collectstatic  Collect static files"
	@echo "  make clean        Remove containers and volumes (WARNING: deletes data)"
	@echo ""

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

migrate:
	docker compose exec web python manage.py migrate

superuser:
	docker compose exec web python manage.py createsuperuser

shell:
	docker compose exec web python manage.py shell_plus

test:
	docker compose exec web pytest tests/ -v

lint:
	docker compose exec web ruff check apps/ config/ tests/

audit:
	docker compose exec web pip-audit

logs:
	docker compose logs -f

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

clean:
	@echo "WARNING: This will delete all containers and volumes including database data."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ]
	docker compose down -v

# Production commands
prod-up:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-migrate:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py migrate

prod-logs:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f
