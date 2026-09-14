.PHONY: up down migrate test backend-shell logs check-docs smoke

up:
	docker compose up --build

down:
	docker compose down

migrate:
	docker compose exec backend alembic upgrade head

test:
	cd backend && . .venv/bin/activate && python3 -m pytest tests/ -v

logs:
	docker compose logs -f backend

check-docs:
	python3 scripts/check_company_docs.py docs/company

smoke:
	cd frontend && npm run build && python3 -m pytest tests -q
