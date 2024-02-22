import unittest
import ulwgl_run
import os
import argparse
from argparse import Namespace
from unittest.mock import patch
from pathlib import Path
from shutil import rmtree
import re
import ulwgl_plugins
import ulwgl_dl_util
import tarfile


class TestGameLauncher(unittest.TestCase):
    """Test suite for ulwgl_run.py."""

    def setUp(self):
        """Create the test directory, exe and environment variables."""
        self.env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "PROTON_CRASH_REPORT_DIR": "/tmp/ULWGL_crashreports",
            "PROTONPATH": "",
            "STEAM_COMPAT_APP_ID": "",
            "STEAM_COMPAT_TOOL_PATHS": "",
            "STEAM_COMPAT_LIBRARY_PATHS": "",
            "STEAM_COMPAT_MOUNTS": "",
            "STEAM_COMPAT_INSTALL_PATH": "",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": "",
            "STEAM_COMPAT_DATA_PATH": "",
            "STEAM_COMPAT_SHADER_PATH": "",
            "FONTCONFIG_PATH": "",
            "EXE": "",
            "SteamAppId": "",
            "SteamGameId": "",
            "STEAM_RUNTIME_LIBRARY_PATH": "",
            "ULWGL_ID": "",
            "STORE": "",
            "PROTON_VERB": "",
        }
        self.test_opts = "-foo -bar"
        # Proton verb
        # Used when testing build_command
        self.test_verb = "waitforexitandrun"
        # Test directory
        self.test_file = "./tmp.WMYQiPb9A"
        # Executable
        self.test_exe = self.test_file + "/" + "foo"
        # Cache
        self.test_cache = Path("./tmp.5HYdpddgvs")
        # Steam compat dir
        self.test_compat = Path("./tmp.ZssGZoiNod")
        # ULWGL-Proton dir
        self.test_proton_dir = Path("ULWGL-Proton-5HYdpddgvs")
        # ULWGL-Proton release
        self.test_archive = Path(self.test_cache).joinpath(
            f"{self.test_proton_dir}.tar.gz"
        )

        self.test_cache.mkdir(exist_ok=True)
        self.test_compat.mkdir(exist_ok=True)
        self.test_proton_dir.mkdir(exist_ok=True)

        # Mock the proton file in the dir
        self.test_proton_dir.joinpath("proton").touch(exist_ok=True)

        # Mock the release downloaded in the cache: tmp.5HYdpddgvs/ULWGL-Proton-5HYdpddgvs.tar.gz
        # Expected directory structure within the archive:
        #
        # +-- ULWGL-Proton-5HYdpddgvs (root directory)
        # |   +-- proton              (normal file)
        with tarfile.open(self.test_archive.as_posix(), "w:gz") as tar:
            tar.add(
                self.test_proton_dir.as_posix(), arcname=self.test_proton_dir.as_posix()
            )

        Path(self.test_file).mkdir(exist_ok=True)
        Path(self.test_exe).touch()

    def tearDown(self):
        """Unset environment variables and delete test files after each test."""
        for key, val in self.env.items():
            if key in os.environ:
                os.environ.pop(key)

        if Path(self.test_file).exists():
            rmtree(self.test_file)

        if self.test_cache.exists():
            rmtree(self.test_cache.as_posix())

        if self.test_compat.exists():
            rmtree(self.test_compat.as_posix())

        if self.test_proton_dir.exists():
            rmtree(self.test_proton_dir.as_posix())

    def test_latest_interrupt(self):
        """Test _get_latest in the event the user interrupts the download/extraction process.

        Assumes a file is being downloaded or extracted in this case.
        A KeyboardInterrupt should be raised, and the cache/compat dir should be cleaned afterwards.
        """
        result = None
        # In the real usage, should be populated after successful callout for latest Proton releases
        # In this case, assume the test variable will be downloaded
        files = [("", ""), (self.test_archive.name, "")]

        # In the event of an interrupt, both the cache/compat dir will be checked for the latest release for removal
        # We do this since the extraction process can be interrupted as well
        ulwgl_dl_util._extract_dir(self.test_archive, self.test_compat)

        with patch("ulwgl_dl_util._fetch_proton") as mock_function:
            # Mock the interrupt
            # We want the dir we tried to extract to be cleaned
            mock_function.side_effect = KeyboardInterrupt
            result = ulwgl_dl_util._get_latest(
                self.env, self.test_compat, self.test_cache, files
            )
            self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to be empty")
            self.assertFalse(result, "Expected None when a ValueError occurs")

            # Verify the state of the compat dir/cache
            self.assertFalse(
                self.test_compat.joinpath(
                    self.test_archive.name[: self.test_archive.name.find(".tar.gz")]
                ).exists(),
                "Expected Proton dir in compat to be cleaned",
            )
            self.assertFalse(
                self.test_cache.joinpath(self.test_archive.name).exists(),
                "Expected Proton dir in compat to be cleaned",
            )

    def test_latest_val_err(self):
        """Test _get_latest in the event something goes wrong in the download process for the latest Proton.

        Assumes a file is being downloaded in this case.
        A ValueError should be raised, and one case it can happen is if the digests mismatched for some reason
        """
        result = None
        # In the real usage, should be populated after successful callout for latest Proton releases
        # When empty, it means the callout failed for some reason (e.g. no internet)
        files = [("", ""), (self.test_archive.name, "")]

        with patch("ulwgl_dl_util._fetch_proton") as mock_function:
            # Mock the interrupt
            mock_function.side_effect = ValueError
            result = ulwgl_dl_util._get_latest(
                self.env, self.test_compat, self.test_cache, files
            )
            self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to be empty")
            self.assertFalse(result, "Expected None when a ValueError occurs")

    def test_latest_offline(self):
        """Test _get_latest when the user doesn't have internet."""
        result = None
        # In the real usage, should be populated after successful callout for latest Proton releases
        # When empty, it means the callout failed for some reason (e.g. no internet)
        files = []

        os.environ["PROTONPATH"] = ""

        with patch("ulwgl_dl_util._fetch_proton"):
            result = ulwgl_dl_util._get_latest(
                self.env, self.test_compat, self.test_cache, files
            )
            self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to be empty")
            self.assertTrue(result is self.env, "Expected the same reference")

    def test_cache_interrupt(self):
        """Test _get_from_cache on keyboard interrupt on extraction from the cache to the compat dir."""
        # In the real usage, should be populated after successful callout for latest Proton releases
        # Just mock it and assumes its the latest
        files = [("", ""), (self.test_archive.name, "")]

        ulwgl_dl_util._extract_dir(self.test_archive, self.test_compat)

        self.assertTrue(
            self.test_compat.joinpath(
                self.test_archive.name[: self.test_archive.name.find(".tar.gz")]
            ).exists(),
            "Expected Proton dir to exist in compat",
        )

        with patch("ulwgl_dl_util._extract_dir") as mock_function:
            with self.assertRaisesRegex(KeyboardInterrupt, ""):
                # Mock the interrupt
                # We want to simulate an interrupt mid-extraction in this case
                # We want the dir we tried to extract to be cleaned
                mock_function.side_effect = KeyboardInterrupt
                ulwgl_dl_util._get_from_cache(
                    self.env, self.test_compat, self.test_cache, files, True
                )

                # After interrupt, we attempt to clean the compat dir for the file we tried to extract because it could be in an incomplete state
                # Verify that the dir we tried to extract from cache is removed to avoid corruption on next launch
                self.assertFalse(
                    self.test_compat.joinpath(
                        self.test_archive.name[: self.test_archive.name.find(".tar.gz")]
                    ).exists(),
                    "Expected Proton dir in compat to be cleaned",
                )

    def test_cache_old(self):
        """Test _get_from_cache when the cache is empty.

        In real usage, this only happens as a last resort when: download fails, digests mismatched, etc.
        """
        result = None
        # In the real usage, should be populated after successful callout for latest Proton releases
        # Just mock it and assumes its the latest
        files = [("", ""), (self.test_archive.name, "")]

        # Mock old Proton versions in the cache
        test_proton_dir = Path("ULWGL-Proton-foo")
        test_proton_dir.mkdir(exist_ok=True)
        test_archive = Path(self.test_cache).joinpath(
            f"{test_proton_dir.as_posix()}.tar.gz"
        )

        with tarfile.open(test_archive.as_posix(), "w:gz") as tar:
            tar.add(test_proton_dir.as_posix(), arcname=test_proton_dir.as_posix())

        result = ulwgl_dl_util._get_from_cache(
            self.env, self.test_compat, self.test_cache, files, False
        )

        # Verify that the old Proton was assigned
        self.assertTrue(result is self.env, "Expected the same reference")
        self.assertEqual(
            self.env["PROTONPATH"],
            self.test_compat.joinpath(
                test_archive.name[: test_archive.name.find(".tar.gz")]
            ).as_posix(),
            "Expected PROTONPATH to be proton dir in compat",
        )

        test_archive.unlink()
        test_proton_dir.rmdir()

    def test_cache_empty(self):
        """Test _get_from_cache when the cache is empty."""
        result = None
        # In the real usage, should be populated after successful callout for latest Proton releases
        # Just mock it and assumes its the latest
        files = [("", ""), (self.test_archive.name, "")]

        self.test_archive.unlink()

        result = ulwgl_dl_util._get_from_cache(
            self.env, self.test_compat, self.test_cache, files, True
        )
        self.assertFalse(result, "Expected None when calling _get_from_cache")
        self.assertFalse(
            self.env["PROTONPATH"],
            "Expected PROTONPATH to be empty when the cache is empty",
        )

    def test_cache(self):
        """Test _get_from_cache.

        Tests the case when the latest Proton already exists in the cache
        """
        result = None
        # In the real usage, should be populated after successful callout for latest Proton releases
        # Just mock it and assumes its the latest
        files = [("", ""), (self.test_archive.name, "")]

        result = ulwgl_dl_util._get_from_cache(
            self.env, self.test_compat, self.test_cache, files, True
        )
        self.assertTrue(result is self.env, "Expected the same reference")
        self.assertEqual(
            self.env["PROTONPATH"],
            self.test_compat.joinpath(
                self.test_archive.name[: self.test_archive.name.find(".tar.gz")]
            ).as_posix(),
            "Expected PROTONPATH to be proton dir in compat",
        )

    def test_steamcompat_nodir(self):
        """Test _get_from_steamcompat when a Proton doesn't exist in the Steam compat dir.

        In this case, the None should be returned to signal that we should continue with downloading the latest Proton
        """
        result = None
        files = [("", ""), (self.test_archive.name, "")]

        result = ulwgl_dl_util._get_from_steamcompat(
            self.env, self.test_compat, self.test_cache, files
        )

        self.assertFalse(result, "Expected None after calling _get_from_steamcompat")
        self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to not be set")

    def test_steamcompat(self):
        """Test _get_from_steamcompat.

        When a Proton exist in .local/share/Steam/compatibilitytools.d, use it when PROTONPATH is unset
        """
        result = None
        files = [("", ""), (self.test_archive.name, "")]

        ulwgl_dl_util._extract_dir(self.test_archive, self.test_compat)

        result = ulwgl_dl_util._get_from_steamcompat(
            self.env, self.test_compat, self.test_cache, files
        )

        self.assertTrue(result is self.env, "Expected the same reference")
        self.assertEqual(
            self.env["PROTONPATH"],
            self.test_compat.joinpath(
                self.test_archive.name[: self.test_archive.name.find(".tar.gz")]
            ).as_posix(),
            "Expected PROTONPATH to be proton dir in compat",
        )

    def test_cleanup_no_exists(self):
        """Test _cleanup when passed files that do not exist.

        In the event of an interrupt during the download/extract process, we only want to clean the files that exist
        NOTE: This is **extremely** important, as we do **not** want to delete anything else but the files we downloaded/extracted -- the incomplete tarball/extracted dir
        """
        result = None

        ulwgl_dl_util._extract_dir(self.test_archive, self.test_compat)

        # Create a file in the cache and compat
        self.test_cache.joinpath("foo").touch()
        self.test_compat.joinpath("foo").touch()

        # Before cleaning
        # On setUp, an archive is created and a dir should exist in compat after extraction
        self.assertTrue(
            self.test_compat.joinpath("foo").exists(),
            "Expected test file to exist in compat before cleaning",
        )
        self.assertTrue(
            self.test_cache.joinpath("foo").exists(),
            "Expected test file to exist in cache before cleaning",
        )
        self.assertTrue(
            self.test_archive.exists(),
            "Expected archive to exist in cache before cleaning",
        )
        self.assertTrue(
            self.test_compat.joinpath(self.test_proton_dir).joinpath("proton").exists(),
            "Expected 'proton' to exist before cleaning",
        )

        # Pass files that do not exist
        result = ulwgl_dl_util._cleanup(
            "foo.tar.gz",
            "foo",
            self.test_cache,
            self.test_compat,
        )

        # Verify state of cache and compat after cleaning
        self.assertFalse(result, "Expected None after cleaning")
        self.assertTrue(
            self.test_compat.joinpath("foo").exists(),
            "Expected test file to exist in compat after cleaning",
        )
        self.assertTrue(
            self.test_cache.joinpath("foo").exists(),
            "Expected test file to exist in cache after cleaning",
        )
        self.assertTrue(
            self.test_compat.joinpath(self.test_proton_dir).exists(),
            "Expected proton dir to still exist after cleaning",
        )
        self.assertTrue(
            self.test_archive.exists(),
            "Expected archive to still exist after cleaning",
        )
        self.assertTrue(
            self.test_compat.joinpath(self.test_proton_dir).joinpath("proton").exists(),
            "Expected 'proton' to still exist after cleaning",
        )

    def test_cleanup(self):
        """Test _cleanup.

        In the event of an interrupt during the download/extract process, we want to clean the cache or the extracted dir in Steam compat to avoid incomplete files
        """
        result = None

        ulwgl_dl_util._extract_dir(self.test_archive, self.test_compat)
        result = ulwgl_dl_util._cleanup(
            self.test_proton_dir.as_posix() + ".tar.gz",
            self.test_proton_dir.as_posix(),
            self.test_cache,
            self.test_compat,
        )
        self.assertFalse(result, "Expected None after cleaning")
        self.assertFalse(
            self.test_compat.joinpath(self.test_proton_dir).exists(),
            "Expected proton dir to be cleaned in compat",
        )
        self.assertFalse(
            self.test_archive.exists(),
            "Expected archive to be cleaned in cache",
        )
        self.assertFalse(
            self.test_compat.joinpath(self.test_proton_dir).joinpath("proton").exists(),
            "Expected 'proton' to not exist after cleaned",
        )

    def test_extract_err(self):
        """Test _extract_dir when passed a non-gzip compressed archive.

        An error should be raised as we only expect .tar.gz releases
        """
        test_archive = self.test_cache.joinpath(f"{self.test_proton_dir}.tar")
        # Do not apply compression
        with tarfile.open(test_archive.as_posix(), "w") as tar:
            tar.add(
                self.test_proton_dir.as_posix(), arcname=self.test_proton_dir.as_posix()
            )

        with self.assertRaisesRegex(tarfile.ReadError, "gzip"):
            ulwgl_dl_util._extract_dir(test_archive, self.test_compat)

        if test_archive.exists():
            test_archive.unlink()

    def test_extract(self):
        """Test _extract_dir.

        An error should not be raised when the Proton release is extracted to the Steam compat dir
        """
        result = None

        result = ulwgl_dl_util._extract_dir(self.test_archive, self.test_compat)
        self.assertFalse(result, "Expected None after extracting")
        self.assertTrue(
            self.test_compat.joinpath(self.test_proton_dir).exists(),
            "Expected proton dir to exists in compat",
        )
        self.assertTrue(
            self.test_compat.joinpath(self.test_proton_dir).joinpath("proton").exists(),
            "Expected 'proton' file to exists in the proton dir",
        )

    def test_game_drive_empty(self):
        """Test enable_steam_game_drive.

        WINE prefixes can be created by passing an empty string
        Example:
        WINEPREFIX= PROTONPATH= GAMEID= ulwgl-run ""

        During this process, we attempt to prepare setting up game drive and set the values for STEAM_RUNTIME_LIBRARY_PATH and STEAM_COMPAT_INSTALL_PATHS
        The resulting value of those variables should be colon delimited string with no leading colons and contain only /usr/lib or /usr/lib32

        Ignores LD_LIBRARY_PATH, relevant to Game Drive, which is sourced in Ubuntu and maybe its derivatives
        """
        args = None
        result_gamedrive = None
        Path(self.test_file + "/proton").touch()

        # Replicate main's execution and test up until enable_steam_game_drive
        with patch("sys.argv", ["", ""]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            # Args
            args = ulwgl_run.parse_args()
            # Config
            ulwgl_run.check_env(self.env)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            ulwgl_run.set_env(self.env, args)

            # Some distributions source this variable (e.g. Ubuntu) and will be added to the result of STEAM_RUNTIME_LIBRARY_PATH
            # Only test the case without it set
            if "LD_LIBRARY_PATH" in os.environ:
                os.environ.pop("LD_LIBRARY_PATH")

            # Game drive
            result_gamedrive = ulwgl_plugins.enable_steam_game_drive(self.env)

        # Ubuntu sources this variable and will be added once Game Drive is enabled
        # Just test the case without it
        if "LD_LIBRARY_PATH" in os.environ:
            os.environ.pop("LD_LIBRARY_PATH")

        for key, val in self.env.items():
            os.environ[key] = val

        # Game drive
        self.assertTrue(result_gamedrive is self.env, "Expected the same reference")
        self.assertTrue(
            self.env["STEAM_RUNTIME_LIBRARY_PATH"],
            "Expected two elements in STEAM_RUNTIME_LIBRARY_PATHS",
        )

        # We just expect /usr/lib and /usr/lib32 since LD_LIBRARY_PATH is unset
        self.assertEqual(
            len(self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":")),
            2,
            "Expected two values in STEAM_RUNTIME_LIBRARY_PATH",
        )

        # We need to sort the elements because the values were originally in a set
        str1, str2 = [*sorted(self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":"))]

        # Check that there are no trailing colons or unexpected characters
        self.assertEqual(str1, "/usr/lib", "Expected /usr/lib")
        self.assertEqual(str2, "/usr/lib32", "Expected /usr/lib32")

        # Both of these values should be empty still after calling enable_steam_game_drive
        self.assertFalse(
            self.env["STEAM_COMPAT_INSTALL_PATH"],
            "Expected STEAM_COMPAT_INSTALL_PATH to be empty when passing an empty EXE",
        )
        self.assertFalse(self.env["EXE"], "Expected EXE to be empty on empty string")

    def test_build_command(self):
        """Test build_command.

        After parsing valid environment variables set by the user, be sure we do not raise a FileNotFoundError
        NOTE: Also, FileNotFoundError will be raised if the _v2-entry-point (ULWGL) is not in $HOME/.local/share/ULWGL or in cwd
        """
        result_args = None
        test_command = []

        # Mock the /proton file
        Path(self.test_file + "/proton").touch()

        with patch("sys.argv", ["", self.test_exe]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            # Args
            result_args = ulwgl_run.parse_args()
            # Config
            ulwgl_run.check_env(self.env)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            ulwgl_run.set_env(self.env, result_args)
            # Game drive
            ulwgl_plugins.enable_steam_game_drive(self.env)

        for key, val in self.env.items():
            os.environ[key] = val

        # Build
        test_command = ulwgl_run.build_command(self.env, test_command)
        self.assertIsInstance(test_command, list, "Expected a List from build_command")
        self.assertEqual(
            len(test_command), 7, "Expected 7 elements in the list from build_command"
        )
        # Verify contents
        entry_point, opt1, verb, opt2, proton, verb2, exe = [*test_command]
        # The entry point dest could change. Just check if there's a value
        self.assertTrue(entry_point, "Expected an entry point")
        self.assertEqual(opt1, "--verb", "Expected --verb")
        self.assertEqual(verb, self.test_verb, "Expected a verb")
        self.assertEqual(opt2, "--", "Expected --")
        self.assertEqual(
            proton,
            Path(self.env.get("PROTONPATH") + "/proton").as_posix(),
            "Expected the proton file",
        )
        self.assertEqual(verb2, self.test_verb, "Expected a verb")
        self.assertEqual(exe, self.env["EXE"], "Expected the EXE")

    def test_set_env_opts(self):
        """Test set_env.

        Ensure no failures and verify that an option is passed to the executable
        """
        result = None
        test_str = "foo"

        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= ulwgl_run foo.exe -foo
        with patch("sys.argv", ["", self.test_exe, test_str]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = test_str
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(result, tuple, "Expected a tuple")
            self.assertIsInstance(result[0], str, "Expected a string")
            self.assertIsInstance(result[1], list, "Expected a list as options")
            self.assertEqual(
                result[0], "./tmp.WMYQiPb9A/foo", "Expected EXE to be unexpanded"
            )
            self.assertEqual(
                *result[1],
                test_str,
                "Expected the test string when passed as an option",
            )
            # Check
            ulwgl_run.check_env(self.env)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            result = ulwgl_run.set_env(self.env, result[0:])
            self.assertTrue(result is self.env, "Expected the same reference")

            path_exe = Path(self.test_exe).expanduser().as_posix()
            path_file = Path(self.test_file).expanduser().as_posix()

            # After calling set_env all paths should be expanded POSIX form
            self.assertEqual(self.env["EXE"], path_exe, "Expected EXE to be expanded")
            self.assertEqual(self.env["STORE"], test_str, "Expected STORE to be set")
            self.assertEqual(
                self.env["PROTONPATH"], path_file, "Expected PROTONPATH to be set"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], path_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(self.env["GAMEID"], test_str, "Expected GAMEID to be set")
            self.assertEqual(
                self.env["PROTON_VERB"],
                self.test_verb,
                "Expected PROTON_VERB to be set",
            )

    def test_set_env_id(self):
        """Test set_env.

        Verify that environment variables (dictionary) are set after calling set_env when passing a valid ULWGL_ID
        When a valid ULWGL_ID is set, the STEAM_COMPAT_APP_ID variables should be the stripped ULWGL_ID
        """
        result = None
        test_str = "foo"
        ulwgl_id = "ulwgl-271590"

        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= ulwgl_run foo.exe
        with patch("sys.argv", ["", self.test_exe]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = ulwgl_id
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(result, tuple, "Expected a tuple")
            self.assertIsInstance(result[0], str, "Expected a string")
            self.assertIsInstance(result[1], list, "Expected a list as options")
            self.assertEqual(
                result[0], "./tmp.WMYQiPb9A/foo", "Expected EXE to be unexpanded"
            )
            self.assertFalse(
                result[1], "Expected an empty list when passing no options"
            )
            # Check
            ulwgl_run.check_env(self.env)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            result = ulwgl_run.set_env(self.env, result[0:])
            self.assertTrue(result is self.env, "Expected the same reference")

            path_exe = Path(self.test_exe).expanduser().as_posix()
            path_file = Path(self.test_file).expanduser().as_posix()

            # After calling set_env all paths should be expanded POSIX form
            self.assertEqual(self.env["EXE"], path_exe, "Expected EXE to be expanded")
            self.assertEqual(self.env["STORE"], test_str, "Expected STORE to be set")
            self.assertEqual(
                self.env["PROTONPATH"], path_file, "Expected PROTONPATH to be set"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], path_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(self.env["GAMEID"], ulwgl_id, "Expected GAMEID to be set")
            self.assertEqual(
                self.env["PROTON_VERB"],
                self.test_verb,
                "Expected PROTON_VERB to be set",
            )
            # ULWGL
            self.assertEqual(
                self.env["ULWGL_ID"],
                self.env["GAMEID"],
                "Expected ULWGL_ID to be GAMEID",
            )
            self.assertEqual(self.env["ULWGL_ID"], ulwgl_id, "Expected ULWGL_ID")
            # Should be stripped -- everything after the hyphen
            self.assertEqual(
                self.env["STEAM_COMPAT_APP_ID"],
                ulwgl_id[ulwgl_id.find("-") + 1 :],
                "Expected STEAM_COMPAT_APP_ID to be the stripped ULWGL_ID",
            )
            self.assertEqual(
                self.env["SteamAppId"],
                self.env["STEAM_COMPAT_APP_ID"],
                "Expected SteamAppId to be STEAM_COMPAT_APP_ID",
            )
            self.assertEqual(
                self.env["SteamGameId"],
                self.env["SteamAppId"],
                "Expected SteamGameId to be STEAM_COMPAT_APP_ID",
            )

            # PATHS
            self.assertEqual(
                self.env["STEAM_COMPAT_SHADER_PATH"],
                self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache",
                "Expected STEAM_COMPAT_SHADER_PATH to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                self.env["PROTONPATH"] + ":" + Path(__file__).parent.as_posix(),
                "Expected STEAM_COMPAT_TOOL_PATHS to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_MOUNTS"],
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                "Expected STEAM_COMPAT_MOUNTS to be set",
            )

    def test_set_env(self):
        """Test set_env.

        Verify that environment variables (dictionary) are set after calling set_env
        """
        result = None
        test_str = "foo"

        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= ulwgl_run foo.exe
        with patch("sys.argv", ["", self.test_exe]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = test_str
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(result, tuple, "Expected a tuple")
            self.assertIsInstance(result[0], str, "Expected a string")
            self.assertIsInstance(result[1], list, "Expected a list as options")
            self.assertEqual(
                result[0], "./tmp.WMYQiPb9A/foo", "Expected EXE to be unexpanded"
            )
            self.assertFalse(
                result[1], "Expected an empty list when passing no options"
            )
            # Check
            ulwgl_run.check_env(self.env)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            result = ulwgl_run.set_env(self.env, result[0:])
            self.assertTrue(result is self.env, "Expected the same reference")

            path_exe = Path(self.test_exe).expanduser().as_posix()
            path_file = Path(self.test_file).expanduser().as_posix()

            # After calling set_env all paths should be expanded POSIX form
            self.assertEqual(self.env["EXE"], path_exe, "Expected EXE to be expanded")
            self.assertEqual(self.env["STORE"], test_str, "Expected STORE to be set")
            self.assertEqual(
                self.env["PROTONPATH"], path_file, "Expected PROTONPATH to be set"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], path_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(self.env["GAMEID"], test_str, "Expected GAMEID to be set")
            self.assertEqual(
                self.env["PROTON_VERB"],
                self.test_verb,
                "Expected PROTON_VERB to be set",
            )
            # ULWGL
            self.assertEqual(
                self.env["ULWGL_ID"],
                self.env["GAMEID"],
                "Expected ULWGL_ID to be GAMEID",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_APP_ID"],
                "0",
                "Expected STEAM_COMPAT_APP_ID to be 0",
            )
            self.assertEqual(
                self.env["SteamAppId"],
                self.env["STEAM_COMPAT_APP_ID"],
                "Expected SteamAppId to be STEAM_COMPAT_APP_ID",
            )
            self.assertEqual(
                self.env["SteamGameId"],
                self.env["SteamAppId"],
                "Expected SteamGameId to be STEAM_COMPAT_APP_ID",
            )

            # PATHS
            self.assertEqual(
                self.env["STEAM_COMPAT_SHADER_PATH"],
                self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache",
                "Expected STEAM_COMPAT_SHADER_PATH to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                self.env["PROTONPATH"] + ":" + Path(__file__).parent.as_posix(),
                "Expected STEAM_COMPAT_TOOL_PATHS to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_MOUNTS"],
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                "Expected STEAM_COMPAT_MOUNTS to be set",
            )

    def test_setup_pfx_mv(self):
        """Test setup_pfx when moving the WINEPREFIX after creating it.

        After setting up the prefix then moving it to a different path, ensure that the symbolic link points to that new location
        """
        result = None
        pattern = r"^/home/[\w\d]+"  # Expects only unicode decimals and alphanumerics
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(self.test_file).cwd().joinpath(self.test_file).as_posix(),
        )
        result = ulwgl_run.setup_pfx(unexpanded_path)

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and tracked_files file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(), "Expected pfx to be a symlink"
        )
        self.assertTrue(
            Path(self.test_file + "/tracked_files").is_file(),
            "Expected tracked_files to be a file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(), "Expected pfx to be a symlink"
        )

        # Check if the symlink is in its unexpanded form
        self.assertEqual(
            Path(self.test_file + "/pfx").readlink().as_posix(),
            Path(unexpanded_path).expanduser().as_posix(),
        )

        old_link = Path(self.test_file + "/pfx").resolve()

        # Rename the dir and replicate passing a new WINEPREFIX
        new_dir = Path(unexpanded_path).expanduser().rename("foo")
        new_unexpanded_path = re.sub(
            pattern,
            "~",
            new_dir.cwd().joinpath("foo").as_posix(),
        )

        ulwgl_run.setup_pfx(new_unexpanded_path)

        new_link = Path("foo/pfx").resolve()
        self.assertTrue(
            old_link is not new_link,
            "Expected the symbolic link to change after moving the WINEPREFIX",
        )

        if new_link.exists():
            rmtree(new_link.as_posix())

    def test_setup_pfx_symlinks(self):
        """Test _setup_pfx for valid symlinks.

        Ensure that symbolic links to the WINE prefix (pfx) are always in expanded form when passed an unexpanded path.
        For example:
        if WINEPREFIX is /home/foo/.wine
        pfx -> /home/foo/.wine

        We do not want the symbolic link such as:
        pfx -> ~/.wine
        """
        result = None
        pattern = r"^/home/[\w\d]+"  # Expects only unicode decimals and alphanumerics
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(self.test_file).cwd().joinpath(self.test_file).as_posix(),
        )
        result = ulwgl_run.setup_pfx(unexpanded_path)

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and tracked_files file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(), "Expected pfx to be a symlink"
        )
        self.assertTrue(
            Path(self.test_file + "/tracked_files").is_file(),
            "Expected tracked_files to be a file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(), "Expected pfx to be a symlink"
        )

        # Check if the symlink is in its unexpanded form
        self.assertEqual(
            Path(self.test_file + "/pfx").readlink().as_posix(),
            Path(unexpanded_path).expanduser().as_posix(),
        )

    def test_setup_pfx_paths(self):
        """Test setup_pfx on unexpanded paths.

        An error should not be raised when passing paths such as ~/path/to/prefix.
        """
        result = None
        pattern = r"^/home/[\w\d]+"  # Expects only unicode decimals and alphanumerics
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(self.test_file).as_posix(),
        )
        result = ulwgl_run.setup_pfx(unexpanded_path)

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and tracked_files file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(), "Expected pfx to be a symlink"
        )
        self.assertTrue(
            Path(self.test_file + "/tracked_files").is_file(),
            "Expected tracked_files to be a file",
        )

    def test_setup_pfx(self):
        """Test setup_pfx."""
        result = None
        result = ulwgl_run.setup_pfx(self.test_file)
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and tracked_files file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(), "Expected pfx to be a symlink"
        )
        self.assertTrue(
            Path(self.test_file + "/tracked_files").is_file(),
            "Expected tracked_files to be a file",
        )

    def test_parse_args(self):
        """Test parse_args with no options.

        There's a requirement to create an empty prefix
        A SystemExit should be raised in this case:
        ./ulwgl_run.py
        """
        with self.assertRaises(SystemExit):
            ulwgl_run.parse_args()

    def test_parse_args_config(self):
        """Test parse_args --config."""
        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=self.test_file),
        ):
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )

    def test_env_proton_nodir(self):
        """Test check_env when $PROTONPATH in the case we failed to set it.

        An FileNotFoundError should be raised when we fail to set PROTONPATH
        """
        # Mock getting the Proton
        with self.assertRaises(FileNotFoundError):
            with patch.object(
                ulwgl_run,
                "get_ulwgl_proton",
                return_value=self.env,
            ):
                os.environ["WINEPREFIX"] = self.test_file
                os.environ["GAMEID"] = self.test_file
                ulwgl_run.check_env(self.env)

    def test_env_wine_dir(self):
        """Test check_env when $WINEPREFIX is not a directory.

        When the user specifies a WINEPREFIX that doesn't exist, make the dirs on their behalf and set it
        An error should not be raised in the process
        """
        # Set a path does not exist
        os.environ["WINEPREFIX"] = "./foo"
        os.environ["GAMEID"] = self.test_file
        os.environ["PROTONPATH"] = self.test_file

        self.assertFalse(
            Path(os.environ["WINEPREFIX"]).exists(),
            "Expected WINEPREFIX to not exist before check_env",
        )

        ulwgl_run.check_env(self.env)

        # After this, the WINEPREFIX and new dirs should be created for the user
        self.assertTrue(
            Path(self.env["WINEPREFIX"]).exists(),
            "Expected WINEPREFIX to exist after check_env",
        )
        self.assertEqual(
            self.env["WINEPREFIX"],
            os.environ["WINEPREFIX"],
            "Expected the WINEPREFIX to be set",
        )

        if Path(self.env["WINEPREFIX"]).is_dir():
            Path(self.env["WINEPREFIX"]).rmdir()

    def test_env_vars_paths(self):
        """Test check_env when setting unexpanded paths for $WINEPREFIX and $PROTONPATH."""
        pattern = r"^/home/[\w\d]+"  # Expects only unicode decimals and alphanumerics
        path_to_tmp = Path(__file__).cwd().joinpath(self.test_file).as_posix()

        # Replace /home/[a-zA-Z]+ substring in path with tilda
        unexpanded_path = re.sub(
            pattern,
            "~",
            path_to_tmp,
        )

        result = None
        os.environ["WINEPREFIX"] = unexpanded_path
        os.environ["GAMEID"] = self.test_file
        os.environ["PROTONPATH"] = unexpanded_path
        result = ulwgl_run.check_env(self.env)
        self.assertTrue(result is self.env, "Expected the same reference")
        self.assertEqual(
            self.env["WINEPREFIX"], unexpanded_path, "Expected WINEPREFIX to be set"
        )
        self.assertEqual(
            self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
        )
        self.assertEqual(
            self.env["PROTONPATH"], unexpanded_path, "Expected PROTONPATH to be set"
        )

    def test_env_vars(self):
        """Test check_env when setting $WINEPREFIX, $GAMEID and $PROTONPATH."""
        result = None
        os.environ["WINEPREFIX"] = self.test_file
        os.environ["GAMEID"] = self.test_file
        os.environ["PROTONPATH"] = self.test_file
        result = ulwgl_run.check_env(self.env)
        self.assertTrue(result is self.env, "Expected the same reference")
        self.assertEqual(
            self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
        )
        self.assertEqual(
            self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
        )
        self.assertEqual(
            self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
        )

    def test_env_vars_proton(self):
        """Test check_env when setting only $WINEPREFIX and $GAMEID."""
        with self.assertRaisesRegex(FileNotFoundError, "Proton"):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            # Mock getting the Proton
            with patch.object(
                ulwgl_run,
                "get_ulwgl_proton",
                return_value=self.env,
            ):
                os.environ["WINEPREFIX"] = self.test_file
                os.environ["GAMEID"] = self.test_file
                result = ulwgl_run.check_env(self.env)
                self.assertTrue(result is self.env, "Expected the same reference")
                self.assertFalse(os.environ["PROTONPATH"])

    def test_env_vars_wine(self):
        """Test check_env when setting only $WINEPREFIX."""
        with self.assertRaisesRegex(ValueError, "GAMEID"):
            os.environ["WINEPREFIX"] = self.test_file
            ulwgl_run.check_env(self.env)

    def test_env_vars_none(self):
        """Tests check_env when setting no env vars.

        GAMEID should be the only strictly required env var
        """
        with self.assertRaisesRegex(ValueError, "GAMEID"):
            ulwgl_run.check_env(self.env)


if __name__ == "__main__":
    unittest.main()
