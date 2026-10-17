.PHONY: setup seed api web test lint build

setup:  ## Install backend and frontend dependencies
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm ci

seed:  ## Create the database and load demo presets
	cd backend && .venv/bin/python manage.py migrate && .venv/bin/python manage.py seed_presets

api:  ## Django API on :8000
	cd backend && .venv/bin/python manage.py runserver 8000

web:  ## Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

test:  ## Backend and frontend tests
	cd backend && .venv/bin/python -m pytest -q
	cd frontend && npm test

lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint && npm run typecheck

build:  ## Production build: React into frontend/dist, served by Django
	cd frontend && npm run build
	cd backend && DJANGO_SECRET_KEY=build .venv/bin/python manage.py collectstatic --noinput
