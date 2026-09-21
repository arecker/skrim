import argparse
import logging
import pathlib
import sys


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
