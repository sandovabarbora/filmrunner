.PHONY: up down migrate test backend-shell logs

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
