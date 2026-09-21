SYSTEM_PYTHON := $(shell which python)

.PHONY: all
all: venv/bin/skrim

venv/bin/python:
	rm -rf ./venv/
	$(SYSTEM_PYTHON) -m venv --copies ./venv
	./venv/bin/pip install --upgrade --quiet pip

venv/bin/skrim: venv/bin/python setup.py
	./venv/bin/pip install --quiet -e .

.PHONY: dev
dev: venv/bin/python setup.py
	./venv/bin/pip install --quiet -e .[dev]

.PHONY: test
test: venv/bin/skrim
	./venv/bin/python -m unittest discover -s tests

.PHONY: clean
clean:
	rm -rf ./venv/
	rm -rf ./skrim.egg-info/
