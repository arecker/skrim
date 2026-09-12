SYSTEM_PYTHON := $(shell which python)

# validate python version matches .python-version
REQUIRED_PYTHON_VERSION := $(shell cat .python-version)
SYSTEM_PYTHON_VERSION := $(shell $(SYSTEM_PYTHON) --version | cut -d' ' -f2)

ifneq ($(SYSTEM_PYTHON_VERSION),$(REQUIRED_PYTHON_VERSION))
$(error system python is $(SYSTEM_PYTHON_VERSION), but .python-version wants $(REQUIRED_PYTHON_VERSION))
endif

venv/bin/python: requirements.txt
	rm -rf ./venv/
	$(SYSTEM_PYTHON) -m venv --copies ./venv
	./venv/bin/pip install --upgrade --quiet pip
	./venv/bin/pip install --quiet -r $<

.PHONY: clean
clean:
	rm -rf ./venv/
