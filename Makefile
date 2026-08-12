COMPOSE = docker compose -f backend/docker-compose.yaml

FRONTEND = npm --prefix frontend

.PHONY: up start dev front down logs migrate revision superuser instructor credits packs psql shell test \
        backup-now restore-drill

up:
	$(COMPOSE) up --build

# Same as `up` but skips the image rebuild — for when the code hasn't changed.
start:
	$(COMPOSE) up

# Everything at once: API/worker/db in the background, Next.js in the foreground
# so its logs and Ctrl-C belong to this terminal. Ctrl-C leaves the backend
# running on purpose — `make down` when you're finished for the day.
dev:
	$(COMPOSE) up -d
	$(FRONTEND) run dev

# Just the Next.js dev server, for when the backend is already up.
front:
	$(FRONTEND) run dev

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
