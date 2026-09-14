# skrim

A single-script Skyrim mod tool. This is a personal project on a Steam Deck — the rules below are deliberate, not defaults to "fix."

## Rules

- No pinned python version. Assert a minimum version at startup (see the existing `validate_python_version` guard) and move on.
- Pip packages are fine, but only installed via the `Makefile`-driven venv (see `Makefile`, `requirements.txt`). The venv must stay completely disposable — rebuildable from scratch with no manual steps, never hand-edited or relied on to persist.
- One script. Everything lives in the `skrim` file, in the `skrim` directory. Do not split into modules/packages.
- No classes. Solve it with standard library objects (functions, namedtuples, dicts, etc).
- No code comments. Docstrings are fine and are the user's to write — see "Docstring-first" below.
- No unit tests. This gets validated by running it against the user's real Skyrim install.
- Don't enforce line length or PEP8 wrapping. Dump code in naturally; the user reformats to taste themselves.
- No `import x as y` and no `from x import y`. Always `import x`, then reference `x.thing`. The user wants the source library visible at every call site.
- Alphabetize the real import block (the one after the python-version guard at the top of the file), e.g. `argparse`, `collections`, `configparser`, `logging`, `pathlib`.

## Workflow: docstring-first

The user writes a function signature and docstring, then hands it off with an empty body for the implementation to be filled in. When asked to "fill out" a function, write only the body — don't touch the signature or docstring wording.

## Workflow: adding a new mod

The user downloads mods from Nexus Mods to `~/Downloads/`. When asked to "move them over" (or similar):

1. Move the archive(s) from `~/Downloads/` into this project's `downloads/` folder.
2. Add a section for each mod to both `test.conf` and `mods.conf`, in the same order in both files. Pick the position based on what the Nexus mod page (or other sources, e.g. the mod's own FOMOD/readme, community load-order guides) recommends — not just appended at the end.
3. Check the mod off in `old-mods.md` if it's listed there.
4. Alert the user if:
   - There are documented compatibility problems between the mod and the user's current Skyrim version.
   - There's no clear reason the mod is still needed, or it doesn't fit a "vanilla plus" playthrough (e.g. it's a large content/overhaul mod, not a bugfix/QoL/light-touch mod).
