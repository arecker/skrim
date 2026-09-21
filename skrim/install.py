import collections
import hashlib
import json
import logging
import pathlib

from .fomod import (
    calculate_fomod_choices,
    calculate_fomod_targets,
    load_fomod_config,
)
from .utils import package_unzipped_in_temp_dir

logger = logging.getLogger()

# A Mod that was already installed, according to the lock file
Installation = collections.namedtuple('Installation', [
    'mod_name',  # mod name from config
    'targets',  # list of absolute paths
    'fomod_choices',  # dict of group name -> chosen plugin name, or None
    'package_hash',  # sha256 hex digest of the downloaded package at install time
])


def load_installations(lockfile_path):
    """Load list of `Installation` tuples from the lockfile."""
    lockfile_path = pathlib.Path(lockfile_path)

    if not lockfile_path.is_file():
        return []

    with lockfile_path.open() as f:
        data = json.load(f)

    return [Installation(**thing) for thing in data]


def write_installations(installations, lockfile_path):
    """Creates a new lockfile."""

    lockfile_path = pathlib.Path(lockfile_path)
    data = [installation._asdict() for installation in installations]

    with lockfile_path.open('w') as f:
        json.dump(data, f, indent=2)


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
