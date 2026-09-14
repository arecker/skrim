"""Unit tests for skrim's Skyrim.ini patching (toggle_ini_patch)."""

import configparser
import pathlib
import tempfile
import unittest

import skrim.__main__ as skrim


class TestToggleIniPatch(unittest.TestCase):

    def write_ini(self, tmp_path, text):
        ini_path = tmp_path / 'Skyrim.ini'
        ini_path.write_text(text)
        return ini_path

    def read_ini(self, ini_path):
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read(ini_path)
        return parser

    def test_on_sets_archive_and_papyrus_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini_path = self.write_ini(pathlib.Path(tmp), '[Archive]\n\n[Papyrus]\nbEnableLogging = 0\nbEnableTrace = 0\n')

            skrim.toggle_ini_patch(ini_path, off=False)

            parser = self.read_ini(ini_path)
            self.assertEqual(parser.get('Archive', 'bInvalidateOlderFiles'), '1')
            self.assertEqual(parser.get('Archive', 'sResourceDataDirsFinal'), '')
            self.assertEqual(parser.get('Papyrus', 'bEnableLogging'), '1')
            self.assertEqual(parser.get('Papyrus', 'bEnableTrace'), '1')

    def test_on_raises_when_archive_section_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini_path = self.write_ini(pathlib.Path(tmp), '[Papyrus]\nbEnableLogging = 0\n')

            with self.assertRaises(ValueError):
                skrim.toggle_ini_patch(ini_path, off=False)

    def test_on_raises_when_papyrus_section_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini_path = self.write_ini(pathlib.Path(tmp), '[Archive]\n')

            with self.assertRaises(ValueError):
                skrim.toggle_ini_patch(ini_path, off=False)

    def test_off_removes_archive_and_papyrus_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini_path = self.write_ini(pathlib.Path(tmp), (
                '[Archive]\n'
                'bInvalidateOlderFiles = 1\n'
                'sResourceDataDirsFinal = \n'
                '\n'
                '[Papyrus]\n'
                'bEnableLogging = 1\n'
                'bEnableTrace = 1\n'
            ))

            skrim.toggle_ini_patch(ini_path, off=True)

            parser = self.read_ini(ini_path)
            self.assertFalse(parser.has_option('Archive', 'bInvalidateOlderFiles'))
            self.assertFalse(parser.has_option('Archive', 'sResourceDataDirsFinal'))
            self.assertFalse(parser.has_option('Papyrus', 'bEnableLogging'))
            self.assertFalse(parser.has_option('Papyrus', 'bEnableTrace'))

    def test_off_is_a_noop_when_sections_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini_path = self.write_ini(pathlib.Path(tmp), '[General]\nsLanguage = ENGLISH\n')

            skrim.toggle_ini_patch(ini_path, off=True)  # should not raise

            parser = self.read_ini(ini_path)
            self.assertEqual(parser.get('General', 'sLanguage'), 'ENGLISH')


if __name__ == '__main__':
    unittest.main()
