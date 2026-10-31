API=apps/api
WEB=apps/web

.PHONY: install api web dev seed reset-demo test
install:            ## one-time setup
	cd $(API) && uv sync
	cd $(WEB) && npm install
api:                ## API on :8000 (auto-reload)
	cd $(API) && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
web:                ## web app on :5173
	cd $(WEB) && npm run dev -- --port 5173
dev:                ## both together
	$(MAKE) -j2 api web
seed reset-demo:    ## restore the exact demo state (real Mongo). With MONGO_URI=memory, just restart the API.
	cd $(API) && .venv/bin/python -m app.seed
test:
	cd $(API) && .venv/bin/python -m pytest -q
	cd $(WEB) && npx tsc --noEmit
