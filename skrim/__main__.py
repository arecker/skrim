"""skrim - manage your skyrim mods like an adult"""

from . import (
    configure_logger,
    hash_package,
    install_mod,
    load_config,
    load_installations,
    parse_args,
    pave_installations,
    sniff_out_skyrim_version,
    toggle_ini_patch,
    toggle_plugins_file,
    write_installations,
)

import logging
import pathlib
import pdb
import sys

logger = logging.getLogger()


def main():
    args = parse_args(description=__doc__)
    configure_logger(verbose=args.verbose)

    logger.debug('starting skrim (python_version = %s, python_cmd = %s, pwd = %s, args = %s)', '.'.join(map(str, sys.version_info[:3])), sys.executable, pathlib.Path.cwd(), args)

    if args.debug:
        logger.info('--debug detected, starting pdb session')
        pdb.set_trace()

    config, mods = load_config(args.config)
    logger.info('loaded %d mod(s) from %s', len(mods), args.config)

    if args.validate:
        logger.info('requirements OK for %d mod(s)', len(mods))
        return

    lock_file = args.config.with_name(f'{args.config.stem}.lock.json')

    installs = load_installations(lock_file)
    logger.info('loaded %d installed mod(s) from %s', len(installs), lock_file)

    old_fomod_choices = {} if args.again else {installation.mod_name: installation.fomod_choices for installation in installs if installation.fomod_choices}

    skyrim_version = sniff_out_skyrim_version(config.game_dir)
    logger.info('sniffed out skyrim version: %s', skyrim_version)

    if args.pave:
        toggle_ini_patch(config.ini_file, off=True)
        toggle_plugins_file(installs, config.plugins_file, off=True)
        pave_installations(installations=installs)
        return

    if args.reinstall:
        mod = next((mod for mod in mods if mod.name == args.reinstall), None)
        if mod is None:
            raise ValueError(f'[{args.reinstall}] not found in {args.config}')

        installs_by_name = {installation.mod_name: installation for installation in installs}
        old_install = installs_by_name.get(args.reinstall)

        if old_install is not None:
            pave_installations(installations=[old_install])
            toggle_plugins_file([old_install], config.plugins_file, off=True)

        install = install_mod(mod, config.downloads_dir, config.game_dir, None, skyrim_version)
        logger.info('copied %d file(s) to game directory', len(install.targets))

        toggle_ini_patch(config.ini_file, off=False)
        toggle_plugins_file([install], config.plugins_file, off=False)

        new_installs = [install if installation.mod_name == args.reinstall else installation for installation in installs]
        if old_install is None:
            new_installs.append(install)

        write_installations(new_installs, lock_file)
        logger.info('wrote %s', lock_file)
        return

    installs_by_name = {installation.mod_name: installation for installation in installs}
    config_mod_names = {mod.name for mod in mods}

    # mods that used to be installed but were dropped from the config: pave them
    dropped = [installation for name, installation in installs_by_name.items() if name not in config_mod_names]
    if dropped:
        pave_installations(installations=dropped)

    # start collecting a list for the new lock file
    new_installs = []

    # names of mods (re)installed this run -- used to cascade reinstalls onto
    # mods that require them, since a dependent's files may overwrite (or be
    # overwritten by) files from what it requires, and reinstalling only one
    # side of that would silently break the overwrite order
    changed = set()

    try:
        for i, mod in enumerate(mods):
            old_install = installs_by_name.get(mod.name)
            package_hash = hash_package(pathlib.Path(config.downloads_dir) / mod.filename)
            requires_changed = any(name in changed for name in mod.requires)

            if old_install is not None and old_install.package_hash == package_hash:
                if not requires_changed and all(pathlib.Path(target).is_file() for target in old_install.targets):
                    logger.info('skipping [%s] (%d/%d), unchanged and all targets present', mod.name, i + 1, len(mods))
                    new_installs.append(old_install)
                    continue
                elif requires_changed:
                    logger.info('reinstalling [%s] (%d/%d), a required mod was updated', mod.name, i + 1, len(mods))
                else:
                    logger.info('reinstalling [%s] (%d/%d), unchanged but missing targets', mod.name, i + 1, len(mods))
            else:
                logger.info('installing [%s] (%d/%d)', mod.name, i + 1, len(mods))
                if old_install is not None:
                    # package changed since last install: pave the old files and
                    # reprompt any fomod choices instead of reusing stale ones
                    pave_installations(installations=[old_install])
                    old_fomod_choices.pop(mod.name, None)

            install = install_mod(mod, config.downloads_dir, config.game_dir, old_fomod_choices.get(mod.name), skyrim_version)
            new_installs.append(install)
            changed.add(mod.name)
            logger.info('copied %d file(s) to game directory', len(install.targets))
    except Exception:
        write_installations(new_installs, lock_file)
        logger.info('wrote partial %s', lock_file)
        raise

    toggle_ini_patch(config.ini_file, off=False)
    logger.info('applied patch to %s', config.ini_file)

    toggle_plugins_file(new_installs, config.plugins_file, off=False)

    write_installations(new_installs, lock_file)
    logger.info('wrote %s', lock_file)


if __name__ == '__main__':
    main()
