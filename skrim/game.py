import configparser
import logging
import pathlib
import re

logger = logging.getLogger()


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
