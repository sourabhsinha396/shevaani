COMPOSE = docker compose -f backend/docker-compose.yaml

.PHONY: up down logs migrate revision superuser instructor credits packs psql shell test \
        backup-now restore-drill

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

# Credit packs the checkout page sells. Idempotent — re-run after a price change.
packs:
	$(COMPOSE) run --rm web python -m app.cli seed-packs

psql:
	$(COMPOSE) exec db psql -U shevaani -d shevaani

# Run the nightly backup by hand, through exactly the code the cron uses.
backup-now:
	$(COMPOSE) run --rm web python -m app.cli backup-now

# The point of the backups work. Restores the newest dump into a throwaway
# database and prints row counts, so "we have backups" is a checked claim rather
# than a belief. Safe to run whenever — it never touches `shevaani`.
restore-drill:
	$(COMPOSE) exec db psql -U shevaani -d postgres \
		-c "DROP DATABASE IF EXISTS shevaani_drill" \
		-c "CREATE DATABASE shevaani_drill"
	$(COMPOSE) run --rm web python -m app.cli restore-drill \
		--target-dsn postgresql://shevaani:shevaani@db:5432/shevaani_drill

shell:
	$(COMPOSE) exec web sh

test:
	$(COMPOSE) run --rm web pytest -q
