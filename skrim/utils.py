import argparse
import contextlib
import libarchive
import logging
import pathlib
import sys
import tempfile
import zipfile

logger = logging.getLogger()


def parse_args(description=None):
    """Return an argparse object.

    Just argparse, only with the courtesy of hiding all of argparse's bullshit.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-c', '--config', type=pathlib.Path, required=True, help='path to the config file (required)')

    options = parser.add_argument_group('Modes', description='(default): installs mods in config')
    options.add_argument('--pave', action='store_true', default=False, help='return skyrim back to its vanilla state')
    options.add_argument('--validate', action='store_true', default=False, help='check mod requirements and exit')
    options.add_argument('--again', action='store_true', default=False, help='prompt interactive installers again')

    run_modes = parser.add_argument_group('Advanced')
    run_modes.add_argument('-v', '--verbose', action='store_true', default=False, help='show debug logs')
    run_modes.add_argument('-d', '--debug', action='store_true', default=False, help='interactively step through code')

    return parser.parse_args()


def configure_logger(verbose=False, format='%(levelname)s: %(message)s'):
    """Setup the script's logger with some good defaults.

    Log everything to stderr with the `format`

    Show debug logs if `verbose` is True, otherwise just stick to info.
    """

    logger = logging.getLogger()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(format))

    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)


@contextlib.contextmanager
def package_unzipped_in_temp_dir(package_path):
    """Extract `package_path` into a temp dir, yielding a `(temp_dir, paths)` tuple.

    `temp_dir` is the `pathlib.Path` to extract into (or the package's single wrapper
    directory within it, if unwrapped -- see below). `paths` is a list of every file in
    the package, as `pathlib.Path`s relative to `temp_dir`.
    """

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
