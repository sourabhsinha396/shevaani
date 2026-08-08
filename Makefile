COMPOSE = docker compose -f backend/docker-compose.yaml

.PHONY: up down logs migrate revision superuser instructor credits psql shell test

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f web worker

migrate:
	$(COMPOSE) run --rm web alembic upgrade head

# make revision m="add waitlist emails"
revision:
	$(COMPOSE) run --rm web alembic revision --autogenerate -m "$(m)"

superuser:
	$(COMPOSE) run --rm web python -m app.cli seed-superuser

instructor:
	$(COMPOSE) run --rm web python -m app.cli create-instructor

# make credits email=learner@example.com n=10
credits:
	$(COMPOSE) run --rm web python -m app.cli grant-credits $(email) $(n)

psql:
	$(COMPOSE) exec db psql -U shevaani -d shevaani

shell:
	$(COMPOSE) exec web sh

test:
	$(COMPOSE) run --rm web pytest -q
