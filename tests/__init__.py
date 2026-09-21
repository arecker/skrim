"""Test suite setup.

Exercising the FOMOD prompt code and the installer prints menus to
stdout and logs warnings (e.g. libarchive CRC quirks) to the root
logger. Neither is useful test output, so silence both here.
"""

import logging
import unittest.mock

logging.disable(logging.CRITICAL)

unittest.mock.patch('builtins.print').start()
