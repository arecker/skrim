"""skrim - manage your skyrim mods like an adult"""

from . import (
    calculate_fomod_choices,
    calculate_fomod_targets,
    configure_logger,
    load_fomod_config,
    parse_args,
)

import collections
import configparser
import contextlib
import hashlib
import json
import libarchive
import logging
import pathlib
import pdb
import re
import sys
import tempfile
import zipfile

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

    lock_file = lock_file_path(args.config)

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

    installs_by_name = {installation.mod_name: installation for installation in installs}
    config_mod_names = {mod.name for mod in mods}

    # mods that used to be installed but were dropped from the config: pave them
    dropped = [installation for name, installation in installs_by_name.items() if name not in config_mod_names]
    if dropped:
        pave_installations(installations=dropped)

    # start collecting a list for the new lock file
    new_installs = []

    try:
        for i, mod in enumerate(mods):
            old_install = installs_by_name.get(mod.name)
            package_hash = hash_package(pathlib.Path(config.downloads_dir) / mod.filename)

            if old_install is not None and old_install.package_hash == package_hash:
                if all(pathlib.Path(target).is_file() for target in old_install.targets):
                    logger.info('skipping [%s] (%d/%d), unchanged and all targets present', mod.name, i + 1, len(mods))
                    new_installs.append(old_install)
                    continue
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


# The [skrim] section of the config file.
Config = collections.namedtuple('Config', [
    'downloads_dir',
    'game_dir',
    'plugins_file',
    'ini_file',
])

# A Mod that is ready to be installed from a downloaded package.
Mod = collections.namedtuple('Mod', [
    'name',
    'filename',
    'requires',
])

# A Mod that was already installed, according to the lock file
Installation = collections.namedtuple('Installation', [
    'mod_name',  # mod name from config
    'targets',  # list of absolute paths
    'fomod_choices',  # dict of group name -> chosen plugin name, or None
    'package_hash',  # sha256 hex digest of the downloaded package at install time
])


def lock_file_path(config_path):
    """Derive the lockfile path from the config file's basename."""
    config_path = pathlib.Path(config_path)
    return config_path.with_name(f'{config_path.stem}.lock.json')


def load_config(config_path):
    """Load the `[skrim]` section and the list of `Mod` tuples from the config path.

    Raises a ValueError if you dicked up, like passed in a path that
    doesn't exist or screwed up your config file.  Take it up with
    python, I'm just using the library!

    Raises a ValueError if [skrim] is missing or any of its fields are missing.

    Returns a (Config, list of Mod) tuple.
    """
    config_path = pathlib.Path(config_path)

    if not config_path.is_file():
        raise ValueError(f'config file does not exist: {config_path}')

    parser = configparser.ConfigParser()

    try:
        parser.read(config_path)
    except configparser.Error as error:
        raise ValueError(f'failed to parse config file {config_path}: {error}') from error

    if not parser.has_section('skrim'):
        raise ValueError(f'[skrim] section missing from {config_path}')

    try:
        config = Config(**dict(parser.items('skrim')))
    except TypeError as e:
        raise ValueError(f'[skrim] is misconfigured! {e}')

    config = config._replace(
        downloads_dir=pathlib.Path(config.downloads_dir).expanduser(),
        game_dir=pathlib.Path(config.game_dir).expanduser().resolve(),
        plugins_file=pathlib.Path(config.plugins_file).expanduser().resolve(),
        ini_file=pathlib.Path(config.ini_file).expanduser().resolve(),
    )

    mods = []

    for section in parser.sections():
        if section == 'skrim':
            continue

        kwargs = dict(parser.items(section))
        requires = tuple(name.strip() for name in kwargs.pop('requires', '').split(',') if name.strip())

        try:
            mod = Mod(name=section, requires=requires, **kwargs)
        except TypeError as e:
            raise ValueError(f'[{section}] is misconfigured! {e}')

        mod_path = config.downloads_dir / mod.filename
        if not mod_path.is_file():
            raise ValueError(f'[{section}] file does not exist: {mod_path}')

        mods.append(mod)

    validate_requirements(mods)

    return config, mods


def validate_requirements(mods):
    """Check that each mod's `requires` entries exist and precede it in `mods`.

    Raises a ValueError on a missing or out-of-order dependency.
    """
    mod_index_by_name = {mod.name: i for i, mod in enumerate(mods)}

    for i, mod in enumerate(mods):
        for required_name in mod.requires:
            required_index = mod_index_by_name.get(required_name)
            if required_index is None:
                raise ValueError(f'[{mod.name}] requires [{required_name}], which is not in config')
            if required_index > i:
                raise ValueError(f'[{mod.name}] requires [{required_name}], which is listed after it in config')


def load_installations(lockfile_path):
    """Load list of `Installation` tuples from the lockfile."""
    lockfile_path = pathlib.Path(lockfile_path)

    if not lockfile_path.is_file():
        return []

    with lockfile_path.open() as f:
        data = json.load(f)

    return [Installation(**thing) for thing in data]


def toggle_ini_patch(ini_path, off=False):
    """Toggle skrim's [Archive] and [Papyrus] changes in the ini at `ini_path`.

    off=True makes it vanilla, off=False makes it mod friendly.
    """

    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(ini_path)

    if off:
        if parser.has_section('Archive'):
            logger.info('removing ini patch from %s', ini_path)
            parser.remove_option('Archive', 'bInvalidateOlderFiles')
            parser.remove_option('Archive', 'sResourceDataDirsFinal')

        if parser.has_section('Papyrus'):
            parser.remove_option('Papyrus', 'bEnableLogging')
            parser.remove_option('Papyrus', 'bEnableTrace')
    else:
        logger.info('adding ini patch to %s', ini_path)

        if not parser.has_section('Archive'):
            raise ValueError(f'[Archive] section missing from {ini_path}')

        parser.set('Archive', 'bInvalidateOlderFiles', '1')
        parser.set('Archive', 'sResourceDataDirsFinal', '')

        if not parser.has_section('Papyrus'):
            raise ValueError(f'[Papyrus] section missing from {ini_path}')

        parser.set('Papyrus', 'bEnableLogging', '1')
        parser.set('Papyrus', 'bEnableTrace', '1')

    with ini_path.open('w') as f:
        parser.write(f)


def toggle_plugins_file(installations, plugins_path, off=False):
    """Toggle skrim-managed plugin entries in the Plugins.txt at `plugins_path`.

    off=True removes the plugins for `installations`, off=False adds them.
    """

    plugin_names = [
        pathlib.Path(target).name
        for installation in installations
        for target in installation.targets
        if pathlib.Path(target).suffix in ('.esp', '.esl', '.esm')
    ]

    lines = plugins_path.read_text().splitlines()
    lines = [line for line in lines if line.lstrip('*') not in plugin_names]

    if off:
        logger.info('removing plugins file patch from %s', plugins_path)
    else:
        logger.info('adding plugins file patch to %s', plugins_path)
        lines += [f'*{name}' for name in plugin_names]

    plugins_path.write_text('\n'.join(lines) + '\n')


def sniff_out_skyrim_version(game_dir):
    """Guess the installed Skyrim version.

    We don't actually parse SkyrimSE.exe as a real PE file -- we just
    search its raw bytes for anything that looks like a version string
    (four dot-separated numbers) and take the biggest one we find.

    Returns None if we can't find SkyrimSE.exe, or nothing version-shaped in it.
    """

    exe_path = pathlib.Path(game_dir) / 'SkyrimSE.exe'

    if not exe_path.is_file():
        return None

    text = exe_path.read_bytes().decode('utf-16-le', errors='ignore')
    versions = re.findall(r'\d+\.\d+\.\d+\.\d+', text)

    if not versions:
        return None

    return max(versions, key=lambda version: tuple(int(part) for part in version.split('.')))


def pave_installations(installations):
    """Delete the existing installations from the game_dir"""

    for installation in installations:
        logger.info('paving [%s]', installation.mod_name)

        for target in installation.targets:
            target_path = pathlib.Path(target)
            logger.debug('deleting [%s] target %s', installation.mod_name, target_path)
            target_path.unlink(missing_ok=True)


def hash_package(package_path):
    """Return the sha256 hex digest of the file at `package_path`."""

    digest = hashlib.sha256()

    with pathlib.Path(package_path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            digest.update(block)

    return digest.hexdigest()


@contextlib.contextmanager
def package_unzipped_in_temp_dir(package_path):
    """Extract `package_path` into a temp dir, yielding the temp dir as a `pathlib.Path`."""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = pathlib.Path(temp_dir)

        if package_path.suffix in ('.7z', '.rar'):
            with libarchive.file_reader(str(package_path)) as archive:
                for entry in archive:
                    entry_path = pathlib.Path(entry.pathname)
                    if entry_path.is_absolute() or '..' in entry_path.parts:
                        raise ValueError(f'unsafe path in archive: {entry.pathname}')

                    target = temp_dir / entry_path
                    target.parent.mkdir(parents=True, exist_ok=True)

                    if entry.isdir:
                        continue

                    written = 0
                    with target.open('wb') as f:
                        try:
                            for block in entry.get_blocks():
                                f.write(block)
                                written += len(block)
                        except libarchive.exception.ArchiveError:
                            # some .rar files trip libarchive's CRC check even though the
                            # bytes it already wrote out are the complete, correct entry --
                            # a known libarchive limitation with certain RAR compression
                            # settings. Only treat it as fatal if we came up short.
                            if written != entry.size:
                                raise
                            logger.warning('ignoring libarchive CRC mismatch for [%s]: got all %d expected bytes anyway', entry.pathname, entry.size)
        else:
            with zipfile.ZipFile(package_path) as archive:
                # the zip spec requires '/' as the separator, but some Windows-built
                # archives (e.g. hand-patched mod zips) store entries with '\' instead.
                # zipfile treats those literally on POSIX, producing a single garbled
                # filename instead of nested dirs, so normalize before extracting.
                for info in archive.infolist():
                    info.filename = info.filename.replace('\\', '/')
                    archive.extract(info, temp_dir)

        # if there is just one directory in the package, then "cd"
        # into it and treat it like the root.  unless that directory is
        # itself a standard Data-relative folder (Data/SKSE/Scripts/etc.),
        # which needs to stay put relative to the game_dir instead of
        # being mistaken for a wrapper folder around the real content.
        special_case_dirs = (
            'data', 'skse', 'interface', 'meshes', 'misc', 'music',
            'scripts', 'seq', 'shadersfx', 'sound', 'strings', 'textures', 'video',
        )
        entries = list(temp_dir.iterdir())
        if len(entries) == 1 and entries[0].is_dir() and entries[0].name.lower() not in special_case_dirs:
            temp_dir = entries[0]

        # Build a full list of file paths in the package.
        paths = [p.relative_to(temp_dir) for p in temp_dir.rglob('*') if p.is_file()]

        yield temp_dir, paths


def install_mod(mod, downloads_dir, game_dir, old_fomod_choices=None, skyrim_version=None):
    """Installs the mod from the package."""

    package_path = pathlib.Path(downloads_dir) / mod.filename
    package_hash = hash_package(package_path)

    logger.info('unpacking [%s]', mod.name)

    with package_unzipped_in_temp_dir(package_path) as (temp_dir, paths):
        if (fomod_config := load_fomod_config(temp_dir, paths)) is not None:
            fomod_choices = calculate_fomod_choices(fomod_config, old_fomod_choices, skyrim_version, game_dir)
            targets = calculate_fomod_targets(fomod_config, fomod_choices, paths, game_dir)
        else:
            fomod_choices = None
            targets = calculate_heuristic_targets(paths)

        assert targets, f'[{mod.name}] did not match any targets and that is a problem!'

        # copy the targets
        copied = []
        try:
            for src, target in targets:
                src = temp_dir / src
                target = (game_dir / target).resolve()
                logger.debug('copying [%s] target %s -> %s', mod.name, src, target)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(src.read_bytes())
                copied.append(target)
        except Exception:
            # don't leave a half-installed mod, so clean up the
            # targets we already copied
            for target in copied:
                if target.is_file():
                    target.unlink()
            raise

    # return it as an installation
    return Installation(mod_name=mod.name, targets=[str(t) for t in copied], fomod_choices=fomod_choices, package_hash=package_hash)


def calculate_heuristic_targets(paths):
    """Take in a list of relative paths, return a list of src/dst pairs.

    Only deals with relative paths.

    This function deals with the loosy goosy spec that is skyrim mods,
    so it's kind of complex.
    """

    targets = []

    # all top level .exe files in root go to the root
    targets += [(p, p) for p in paths if p.full_match('*.exe')]

    # all .dll files in root go to the root
    targets += [(p, p) for p in paths if p.full_match('*.dll')]

    # everything under a Data/ dir gets mirrored into game_dir/Data
    targets += [(p, pathlib.Path('Data', *p.parts[1:])) for p in paths if p.parts[0].lower() == 'data']

    # everything under a bare SKSE/ dir gets mirrored into game_dir/Data/SKSE
    targets += [(p, pathlib.Path('Data/') / p) for p in paths if p.full_match('SKSE/**')]

    # plugin/archive files loose in the root go into game_dir/Data
    for ext in ('.esp', '.esl', '.esm', '.bsa', '.bsl', '.ini'):
        targets += [(p, pathlib.Path('Data') / p) for p in paths if p.full_match(f'*{ext}')]

    # any other top level directory is assumed to be Data-relative content shipped without the Data/ wrapper
    accounted_for_dirs = ('data', 'skse')
    targets += [(p, pathlib.Path('Data') / p) for p in paths if len(p.parts) > 1 and p.parts[0].lower() not in accounted_for_dirs]

    return targets


def write_installations(installations, lockfile_path):
    """Creates a new lockfile."""

    lockfile_path = pathlib.Path(lockfile_path)
    data = [installation._asdict() for installation in installations]

    with lockfile_path.open('w') as f:
        json.dump(data, f, indent=2)


if __name__ == '__main__':
    main()
