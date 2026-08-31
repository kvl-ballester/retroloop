.PHONY: install test lint format check run migrate

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

check: lint format-check

format-check:
	uv run ruff format --check .

run:
	uv run manage.py runserver

migrate:
	uv run manage.py migrate
