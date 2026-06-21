.PHONY: test test-api test-web verify run-api run-web

test:
	.venv/bin/python -m pytest -q

test-api:
	.venv/bin/python -m pytest -q
	.venv/bin/python -m compileall -q apps/api tests

test-web:
	cd apps/web && npm run build

verify: test-api test-web

run-api:
	.venv/bin/uvicorn kerislab.main:app --app-dir apps/api --reload --host 0.0.0.0 --port 8000

run-web:
	cd apps/web && VITE_API_BASE_URL=http://localhost:8000 npm run dev
