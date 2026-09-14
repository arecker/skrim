"""Unit tests for skrim's archive unpacking (package_unzipped_in_temp_dir)."""

import contextlib
import pathlib
import unittest
import unittest.mock
import zipfile

import skrim.__main__ as skrim


class FakeRarEntry:
    """Stand-in for a libarchive entry whose get_blocks() can raise partway through."""

    def __init__(self, pathname, size, blocks, isdir=False):
        self.pathname = pathname
        self.size = size
        self.isdir = isdir
        self._blocks = blocks

    def get_blocks(self):
        for block in self._blocks:
            if isinstance(block, Exception):
                raise block
            yield block


class TestPackageUnzippedInTempDir(unittest.TestCase):

    def make_zip(self, tmp_path, *names):
        package_path = tmp_path / 'package.zip'
        with zipfile.ZipFile(package_path, 'w') as archive:
            for name in names:
                archive.writestr(name, b'')
        return package_path

    def test_single_wrapper_directory_is_stripped(self):
        with skrim.tempfile.TemporaryDirectory() as tmp:
            package_path = self.make_zip(pathlib.Path(tmp), 'SomeMod/plugin.esp', 'SomeMod/readme.txt')

            with skrim.package_unzipped_in_temp_dir(package_path) as (temp_dir, paths):
                self.assertCountEqual(paths, [pathlib.Path('plugin.esp'), pathlib.Path('readme.txt')])

    def test_bare_data_directory_is_not_stripped(self):
        with skrim.tempfile.TemporaryDirectory() as tmp:
            package_path = self.make_zip(pathlib.Path(tmp), 'Data/plugin.esp')

            with skrim.package_unzipped_in_temp_dir(package_path) as (temp_dir, paths):
                self.assertCountEqual(paths, [pathlib.Path('Data/plugin.esp')])

    def test_bare_scripts_directory_is_not_stripped(self):
        # regression test: a package whose only top-level folder is a standard
        # Data subfolder (e.g. Scripts, Meshes) must keep that folder name --
        # it's real content, not a wrapper directory around the real content.
        with skrim.tempfile.TemporaryDirectory() as tmp:
            package_path = self.make_zip(pathlib.Path(tmp), 'Scripts/TrapBear.pex')

            with skrim.package_unzipped_in_temp_dir(package_path) as (temp_dir, paths):
                self.assertCountEqual(paths, [pathlib.Path('Scripts/TrapBear.pex')])

            targets = skrim.calculate_heuristic_targets(paths)
            self.assertEqual(targets, [(pathlib.Path('Scripts/TrapBear.pex'), pathlib.Path('Data/Scripts/TrapBear.pex'))])

    def test_bare_meshes_directory_is_not_stripped(self):
        with skrim.tempfile.TemporaryDirectory() as tmp:
            package_path = self.make_zip(pathlib.Path(tmp), 'Meshes/thing.nif')

            with skrim.package_unzipped_in_temp_dir(package_path) as (temp_dir, paths):
                self.assertCountEqual(paths, [pathlib.Path('Meshes/thing.nif')])

    def test_rar_crc_mismatch_is_tolerated_once_all_bytes_are_written(self):
        # regression test: some .rar files trip libarchive's CRC check even though it
        # already wrote out the complete, correct entry -- a known libarchive limitation
        # with certain RAR compression settings, not real corruption.
        entry = FakeRarEntry('ok.bsa', size=6, blocks=[b'abc', b'def', skrim.libarchive.exception.ArchiveError('File CRC error')])

        with skrim.tempfile.TemporaryDirectory() as tmp:
            package_path = pathlib.Path(tmp) / 'package.rar'
            with unittest.mock.patch.object(skrim.libarchive, 'file_reader', return_value=contextlib.nullcontext([entry])):
                with skrim.package_unzipped_in_temp_dir(package_path) as (temp_dir, paths):
                    self.assertEqual(paths, [pathlib.Path('ok.bsa')])
                    self.assertEqual((temp_dir / 'ok.bsa').read_bytes(), b'abcdef')

    def test_rar_crc_mismatch_still_raises_when_bytes_are_actually_short(self):
        entry = FakeRarEntry('bad.bsa', size=100, blocks=[b'abc', skrim.libarchive.exception.ArchiveError('File CRC error')])

        with skrim.tempfile.TemporaryDirectory() as tmp:
            package_path = pathlib.Path(tmp) / 'package.rar'
            with unittest.mock.patch.object(skrim.libarchive, 'file_reader', return_value=contextlib.nullcontext([entry])):
                with self.assertRaises(skrim.libarchive.exception.ArchiveError):
                    with skrim.package_unzipped_in_temp_dir(package_path):
                        pass


class TestCalculateHeuristicTargets(unittest.TestCase):

    def test_loose_esm_goes_to_data(self):
        # regression test: a bare master file (.esm) shipped loose at the archive root
        # must be recognized just like .esp/.esl -- Legacy of the Dragonborn ships exactly
        # this way, and a missed .esm silently drops the mod's entire master file with no
        # error (other loose files still match, so the "did not match any targets" assert
        # never fires).
        paths = [pathlib.Path('SomeMod.esm')]
        targets = skrim.calculate_heuristic_targets(paths)
        self.assertEqual(targets, [(pathlib.Path('SomeMod.esm'), pathlib.Path('Data/SomeMod.esm'))])

    def test_loose_esp_esl_bsa_bsl_ini_go_to_data(self):
        paths = [pathlib.Path(f'SomeMod{ext}') for ext in ('.esp', '.esl', '.bsa', '.bsl', '.ini')]
        targets = skrim.calculate_heuristic_targets(paths)
        self.assertCountEqual(targets, [(p, pathlib.Path('Data') / p) for p in paths])


if __name__ == '__main__':
    unittest.main()
