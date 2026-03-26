.PHONY: install dev test lint format run-api run-ui docker-build docker-up

install:
	pip install .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/unit -v

test-all:
	pytest -v

lint:
	ruff check src/ tests/
	mypy src/email_rag/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

run-api:
	uvicorn email_rag.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload

run-ui:
	streamlit run src/email_rag/ui/app.py

docker-build:
	docker compose build

docker-up:
	docker compose up -d
