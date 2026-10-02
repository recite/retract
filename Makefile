PYTHON ?= python

.PHONY: install format lint test check ci-docker docker-test benchmark
install:
	$(PYTHON) -m pip install -e '.[dev]'

format:
	$(PYTHON) -m black retract tests evaluation
	$(PYTHON) -m isort retract tests evaluation

lint:
	$(PYTHON) -m black --check retract tests evaluation
	$(PYTHON) -m isort --check-only retract tests evaluation
	$(PYTHON) -m flake8 retract tests evaluation

test:
	$(PYTHON) -m pytest

check: lint test

ci-docker:
	COPYFILE_DISABLE=1 tar --exclude=.git --exclude=.venv --exclude=build --exclude=dist -cf - . | docker run --rm -i -w /work python:3.14-slim sh -c "tar -xf - && pip install -e '.[dev]' && python -m black --check retract tests evaluation && python -m isort --check-only retract tests evaluation && python -m flake8 retract tests evaluation && python -m pytest"

docker-test:
	docker build -t retract-test .
	@container=$$(docker create --network none -e GITHUB_WORKSPACE=/tmp/fixtures retract-test --paths sample.bib --database /tmp/fixtures/notices.csv --dry-run --report /tmp/report.json); \
	trap 'docker rm -f "$$container" >/dev/null' EXIT; \
	docker cp tests/fixtures "$$container:/tmp/fixtures"; \
	docker start --attach "$$container"; \
	exit $$(docker inspect --format '{{.State.ExitCode}}' "$$container")

benchmark:
	$(PYTHON) -m evaluation.benchmark
