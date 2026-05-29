# Convenience targets for local (non-Docker) development.
# The canonical single-command setup is `docker compose up` (see README).

.PHONY: help up down logs backend frontend test install-backend install-frontend

help:
	@echo "Targets:"
	@echo "  make up               - docker compose up (full stack, single command)"
	@echo "  make down             - docker compose down"
	@echo "  make logs             - tail backend logs"
	@echo "  make backend          - run backend locally (uvicorn, reload)"
	@echo "  make frontend         - run frontend locally (vite dev)"
	@echo "  make test             - run backend test suite"
	@echo "  make install-backend  - create venv + install backend deps"
	@echo "  make install-frontend - install frontend deps"

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend

install-backend:
	cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/python -m pytest -q
