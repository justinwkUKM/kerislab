.PHONY: test test-api test-web verify migrate run-api run-web compose-config compose-preflight compose-up compose-smoke compose-backup compose-restore compose-down compose-logs

test:
	.venv/bin/python -m pytest -q

test-api:
	.venv/bin/python -m pytest -q
	.venv/bin/python -m compileall -q apps/api tests

test-web:
	cd apps/web && npm run build

verify: test-api test-web

migrate:
	PYTHONPATH=apps/api .venv/bin/python -c "from kerislab.migrations import apply_configured_migrations; print(apply_configured_migrations())"

run-api:
	.venv/bin/uvicorn kerislab.main:app --app-dir apps/api --reload --host 0.0.0.0 --port 8000

run-web:
	cd apps/web && VITE_API_BASE_URL=http://localhost:8000 npm run dev

compose-config:
	docker compose config

compose-preflight:
	.venv/bin/python scripts/compose_preflight.py

compose-up:
	docker compose up --build

compose-smoke:
	docker compose up --build -d
	.venv/bin/python scripts/compose_smoke.py

compose-backup:
	.venv/bin/python scripts/compose_backup.py

compose-restore:
	.venv/bin/python scripts/compose_restore.py $(RESTORE_DIR)

compose-down:
	docker compose down

compose-logs:
	docker compose logs -f
