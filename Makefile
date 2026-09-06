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

.PHONY: prod
prod: venv/bin/python
	./skrim \
		--downloads-dir ./downloads \
		--lock-file ./mods.json.lock \
		--game-dir "$(HOME)/.local/share/Steam/steamapps/common/Skyrim Special Edition" \
		--plugins-file "$(HOME)/.local/share/Steam/steamapps/compatdata/489830/pfx/drive_c/users/steamuser/AppData/Local/Skyrim Special Edition/Plugins.txt" \
		--ini-file "$(HOME)/.local/share/Steam/steamapps/compatdata/489830/pfx/drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition/Skyrim.ini"

.PHONY: test
test: venv/bin/python
	./skrim \
		--downloads-dir ./downloads \
		--lock-file ./mocks.json.lock \
		--game-dir ./mocks/game_dir \
		--plugins-file ./mocks/Plugins.txt \
		--ini-file ./mocks/Skyrim.ini
