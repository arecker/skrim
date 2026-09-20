"""Unit tests for skrim's config loading (load_config), focused on `requires`."""

import pathlib
import tempfile
import unittest

import skrim.__main__ as skrim


class TestLoadConfigRequires(unittest.TestCase):

    def write_config(self, tmp_path, mods_text):
        downloads_dir = tmp_path / 'downloads'
        downloads_dir.mkdir()
        (downloads_dir / 'a.7z').touch()
        (downloads_dir / 'b.7z').touch()
        (downloads_dir / 'c.7z').touch()

        config_path = tmp_path / 'mods.conf'
        config_path.write_text(
            '[skrim]\n'
            f'downloads_dir = {downloads_dir}\n'
            'game_dir = .\n'
            'plugins_file = .\n'
            'ini_file = .\n'
            '\n'
            f'{mods_text}'
        )
        return config_path

    def test_requires_defaults_to_empty_tuple(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self.write_config(pathlib.Path(tmp), '[a]\nfilename = a.7z\n')

            _, mods = skrim.load_config(config_path)

            self.assertEqual(mods[0].requires, ())

    def test_requires_met_in_order_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self.write_config(pathlib.Path(tmp), (
                '[a]\nfilename = a.7z\n\n'
                '[b]\nfilename = b.7z\nrequires = a\n'
            ))

            _, mods = skrim.load_config(config_path)

            self.assertEqual(mods[1].requires, ('a',))

    def test_requires_multiple_comma_separated(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self.write_config(pathlib.Path(tmp), (
                '[a]\nfilename = a.7z\n\n'
                '[b]\nfilename = b.7z\n\n'
                '[c]\nfilename = c.7z\nrequires = a, b\n'
            ))

            _, mods = skrim.load_config(config_path)

            self.assertEqual(mods[2].requires, ('a', 'b'))

    def test_requires_unknown_mod_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self.write_config(pathlib.Path(tmp), '[a]\nfilename = a.7z\nrequires = nonexistent\n')

            with self.assertRaises(ValueError):
                skrim.load_config(config_path)

    def test_requires_listed_after_dependent_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = self.write_config(pathlib.Path(tmp), (
                '[a]\nfilename = a.7z\nrequires = b\n\n'
                '[b]\nfilename = b.7z\n'
            ))

            with self.assertRaises(ValueError):
                skrim.load_config(config_path)


if __name__ == '__main__':
    unittest.main()
