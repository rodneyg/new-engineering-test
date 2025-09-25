PY = uv run
UV_ENV = UV_CACHE_DIR=.uvcache

.PHONY: help uv-sync migrate makemigrations run test build-frontend clean lint format

help:
	@echo "Targets:"
	@echo "  uv-sync           Install Python deps via uv"
	@echo "  makemigrations    Create new Django migrations"
	@echo "  migrate           Apply database migrations"
	@echo "  run               Start Django dev server"
	@echo "  test              Run pytest"
	@echo "  build-frontend    Build Vite+Tailwind assets to static/app/"
	@echo "  lint              Run ESLint on frontend"
	@echo "  format            Run Prettier write formatting"
	@echo "  clean             Remove build artifacts"

uv-sync:
	$(UV_ENV) uv sync

makemigrations:
	$(UV_ENV) $(PY) python manage.py makemigrations

migrate:
	$(UV_ENV) $(PY) python manage.py migrate

run:
	$(UV_ENV) $(PY) python manage.py runserver

test:
	$(UV_ENV) $(PY) pytest -q

build-frontend:
	npm install
	npm run build

lint:
	npm run lint

format:
	npm run format

clean:
	rm -rf static/app/* **/__pycache__ .pytest_cache
