# Makefile для Windows (через WSL или Git Bash)
# Использование: mingw32-make или make (если установлен через WSL)

.PHONY: help up down build logs init-db clean shell

help:
	@echo "Available commands:"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make build       - Build Docker images"
	@echo "  make logs        - View logs"
	@echo "  make init-db     - Initialize database"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make shell       - Enter manager container shell"

up:
	docker-compose up -d
	@echo ""
	@echo "========================================"
	@echo "Services started!"
	@echo "  Manager gRPC: localhost:50051"
	@echo "  PostgreSQL:   localhost:5432"
	@echo "========================================"
	@echo ""
	@echo "View logs: make logs"

down:
	docker-compose down

build:
	docker-compose build --no-cache

logs:
	docker-compose logs -f --tail=100

init-db:
	docker-compose exec manager python -c "import asyncio; from src.db.session import init_db; asyncio.run(init_db())"
	@echo "Database initialized"

clean:
	@echo "Cleaning Python cache files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>nul || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>nul || true
	find . -type f -name "*.pyc" -delete 2>nul || true
	@echo "Cleaned"

shell:
	docker-compose exec manager bash

psql:
	docker-compose exec postgres psql -U dcap -d dcap

restart: down up

status:
	docker-compose ps