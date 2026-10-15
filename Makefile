.PHONY: up down test lint format security

PYTHON ?= python
DOCKER_COMPOSE ?= docker compose

up:
	$(DOCKER_COMPOSE) up --build -d

down:
	$(DOCKER_COMPOSE) down --remove-orphans

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

security:
	$(PYTHON) -m bandit -r app -q
