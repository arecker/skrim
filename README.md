# skrim

Manage your skyrim mods like an adult!  No winetricks!  No vortex!  No fuss!

_Built on a steam deck for the steam deck._

## Install

Switch to desktop mode!  Open a terminal and clone this repo!

```
$ git clone https://www.github.com/arecker/skrim.git
```

Run `make` in this directory!

```
$ make
rm -rf ./venv/
/usr/bin/python -m venv --copies ./venv
./venv/bin/pip install --upgrade --quiet pip
./venv/bin/pip install --quiet -e .
```

Put this alias in your `~/.bashrc`!

_Pssst.  Use the ACTUAL path to where you cloned it.  You can do it, I believe in you._

```
alias skrim="$HOME/src/skrim/venv/bin/skrim"
```

You can now use `skrim` to manage your skyrim mods!

## Usage

Open a terminal.  Create a conf file that looks like this!

```
# mods.conf

[skrim]
downloads_dir = ./downloads
game_dir = ~/.local/share/Steam/steamapps/common/Skyrim Special Edition
plugins_file = ~/.local/share/Steam/steamapps/compatdata/489830/pfx/drive_c/users/steamuser/AppData/Local/Skyrim Special Edition/Plugins.txt
ini_file = ~/.local/share/Steam/steamapps/compatdata/489830/pfx/drive_c/users/steamuser/Documents/My Games/Skyrim Special Edition/Skyrim.ini
```

_You should double check these values.  This is only what my game looks like.  Yours probably looks the same too, but just make sure these all point to real files!_

Start adding your mods!  Download the packages to `downloads_dir` and put em in the config file!

```
# mods.conf

# ...

[skse64]
filename = Skyrim Script Extender (SKSE64) Steam 30379 2.3.1 2026-08-27T16-52Z s6Og0dG94.7z

[address_library]
filename = Address Library All in One (1.7.104.0) v13 32444 13 2026-08-27T15-29Z Ae46W7Fw2.zip

[ussep]
filename = Unofficial Skyrim Special Edition Patch 266 4.3.9c 2026-09-05T22-22Z lNkz9LChN.7z
```

Let it rip!  Watch that baby purr!  Don't delete the free lockfile it generates, it uses that to know what the HECK is going on!

## Features

Need to make a change?  Just change the config and run it again!  It's _**idempotent**_ - ya dangus.

Have all sorts of complicated dependencies?  I GOT YOU.  Just use `requires` in the mod to name another mod.

```
[open_shaders]
filename = Open Shaders 180419 2.13.0 2026-09-17T05-46Z s6Og0dpzV.7z
requires = address_library, skse64, engine_fixes

[ussep]
filename = Unofficial Skyrim Special Edition Patch 266 4.3.9c 2026-09-05T22-22Z lNkz9LChN.7z

[cutting_room_floor]
filename = Cutting Room Floor 276 3.1.26 2026-08-28T05-29Z RHaV1OLK3.7z
requires = ussep
```

And if the BIG mod changes, the others will get REINSTALLED FOR FREE.  I DON'T EVEN WANT YOUR MONEY!

Wait, Alex.  Some mods have fancy prompts that require user input.  How the heck am I supposed to do that.  WITH YOUR TERMINAL, DUM DUM.  It's gonna prompt you for options and defaults, don't even worry about it my boy.  Your answers will be saved in the lockfile unless you run the tool with `--again`.

Tired of your mods?  Get rid of everything with `--pave`.  This will COMPLETELY reset your game to the way Todd Howard intended.

```
$ skrim -c mods.conf --pave
```

How do you configure load order?  Load order?  The way you list the mods IS the load order.

### Fancy Things

Run with DEBUG logs.

```
$ skrim -v
```

Run with an interactive debugger.

```
$ skrim -d
```

Anything else?  Just run `skrim -h`
