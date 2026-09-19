# skrim

A Skyrim mod tool for managing mods on a Steam Deck.

## Workflow: adding a new mod

The user downloads mods from Nexus Mods to `~/Downloads/`. When asked to "move them over" (or similar):

1. Move the archive(s) from `~/Downloads/` into this project's `downloads/` folder.
2. Add a section for the mod to `mods.conf`. Pick the position based on what the Nexus mod page (or other sources, e.g. the mod's own FOMOD/readme, community load-order guides) recommends — not just appended at the end.
3. Check the mod off in `old-mods.md` if it's listed there.
4. Alert the user if:
   - There are documented compatibility problems between the mod and the user's current Skyrim version.
   - There's no clear reason the mod is still needed, or it doesn't fit a "vanilla plus" playthrough (e.g. it's a large content/overhaul mod, not a bugfix/QoL/light-touch mod).
