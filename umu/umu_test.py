import unittest
import umu_run
import os
import argparse
import re
import umu_dl_util
import tarfile
import umu_util
import hashlib
import json
from argparse import Namespace
from unittest.mock import patch
from pathlib import Path
from shutil import rmtree, copytree, copy
from pwd import getpwuid
from subprocess import CompletedProcess


class TestGameLauncher(unittest.TestCase):
    """Test suite for umu_run.py."""

    def setUp(self):
        """Create the test directory, exe and environment variables."""
        self.env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "PROTON_CRASH_REPORT_DIR": "/tmp/umu_crashreports",
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
            "UMU_ID": "",
            "STORE": "",
            "PROTON_VERB": "",
        }
        self.user = getpwuid(os.getuid()).pw_name
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
        # umu-proton dir
        self.test_proton_dir = Path("UMU-Proton-5HYdpddgvs")
        # umu-proton release
        self.test_archive = Path(self.test_cache).joinpath(
            f"{self.test_proton_dir}.tar.gz"
        )
        # /usr/share/umu
        self.test_user_share = Path("./tmp.BXk2NnvW2m")
        # ~/.local/share/Steam/compatibilitytools.d
        self.test_local_share = Path("./tmp.aDl73CbQCP")

        # Dictionary that represents the umu_versionS.json
        self.root_config = {
            "umu": {
                "versions": {
                    "launcher": "0.1-RC3",
                    "runner": "0.1-RC3",
                    "runtime_platform": "sniper_platform_0.20240125.75305",
                    "reaper": "1.0",
                    "pressure_vessel": "v0.20240212.0",
                }
            }
        }
        # umu_version.json
        self.test_config = json.dumps(self.root_config, indent=4)

        self.test_user_share.mkdir(exist_ok=True)
        self.test_local_share.mkdir(exist_ok=True)
        self.test_cache.mkdir(exist_ok=True)
        self.test_compat.mkdir(exist_ok=True)
        self.test_proton_dir.mkdir(exist_ok=True)

        # Mock a valid configuration file at /usr/share/umu:
        # tmp.BXk2NnvW2m/umu_version.json
        Path(self.test_user_share, "umu_version.json").touch()
        with Path(self.test_user_share, "umu_version.json").open(
            mode="w", encoding="utf-8"
        ) as file:
            file.write(self.test_config)

        # Mock the launcher files
        Path(self.test_user_share, "umu_consts.py").touch()
        Path(self.test_user_share, "umu_dl_util.py").touch()
        Path(self.test_user_share, "umu_log.py").touch()
        Path(self.test_user_share, "umu_plugins.py").touch()
        Path(self.test_user_share, "umu_run.py").touch()
        Path(self.test_user_share, "umu_util.py").touch()
        Path(self.test_user_share, "umu-run").symlink_to("umu_run.py")

        # Mock the runtime files
        Path(self.test_user_share, "sniper_platform_0.20240125.75305").mkdir()
        Path(self.test_user_share, "sniper_platform_0.20240125.75305", "foo").touch()
        Path(self.test_user_share, "run").touch()
        Path(self.test_user_share, "run-in-sniper").touch()
        Path(self.test_user_share, "umu").touch()

        # Mock pressure vessel
        Path(self.test_user_share, "pressure-vessel", "bin").mkdir(parents=True)
        Path(self.test_user_share, "pressure-vessel", "foo").touch()
        Path(self.test_user_share, "pressure-vessel", "bin", "pv-verify").touch()

        # Mock the proton file in the dir
        self.test_proton_dir.joinpath("proton").touch(exist_ok=True)

        # Mock the release downloaded in the cache:
        # tmp.5HYdpddgvs/umu-Proton-5HYdpddgvs.tar.gz
        # Expected directory structure within the archive:
        #
        # +-- umu-Proton-5HYdpddgvs (root directory)
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

        if self.test_user_share.exists():
            rmtree(self.test_user_share.as_posix())

        if self.test_local_share.exists():
            rmtree(self.test_local_share.as_posix())

    def test_check_runtime(self):
        """Test check_runtime when pv-verify does not exist.

        check_runtime calls pv-verify to verify the integrity of the runtime
        archive's contents, and will only be called when restoring or setting
        up the runtime

        If the pv-verify binary does not exist, a warning should be logged and
        the function should return
        """
        json_root = umu_util._get_json(self.test_user_share, "umu_version.json")
        self.test_user_share.joinpath("pressure-vessel", "bin", "pv-verify").unlink()
        result = umu_util.check_runtime(self.test_user_share, json_root)
        self.assertEqual(result, 1, "Expected the exit code 1")

    def test_check_runtime_fail(self):
        """Test check_runtime when runtime validation fails."""
        json_root = umu_util._get_json(self.test_user_share, "umu_version.json")
        mock = CompletedProcess(["foo"], 1)
        with patch.object(umu_util, "run", return_value=mock):
            result = umu_util.check_runtime(self.test_user_share, json_root)
            self.assertEqual(result, 1, "Expected the exit code 1")

    def test_check_runtime_success(self):
        """Test check_runtime when runtime validation succeeds."""
        json_root = umu_util._get_json(self.test_user_share, "umu_version.json")
        mock = CompletedProcess(["foo"], 0)
        with patch.object(umu_util, "run", return_value=mock):
            result = umu_util.check_runtime(self.test_user_share, json_root)
            self.assertEqual(result, 0, "Expected the exit code 0")

    def test_move(self):
        """Test _move when copying a directory or a file.

        This function simply wraps shutil.move but deletes the dest directory
        before moving the source directory. While not strictly necesssary,
        doing this maintains the integrity of the runtime platform's directory
        tree defined in the mtree.txt.gz file
        """
        test_dir = self.test_user_share.joinpath("foo")
        test_file = self.test_user_share.joinpath("bar")
        test_dir.mkdir()
        test_file.touch()
        self.test_user_share.joinpath("qux").symlink_to(test_file)

        # Directory
        umu_util._move(test_dir, self.test_user_share, self.test_local_share)
        self.assertFalse(
            self.test_user_share.joinpath("foo").exists(), "foo did not move from src"
        )
        self.assertTrue(
            self.test_local_share.joinpath("foo").exists(), "foo did not move to dst"
        )

        # File
        umu_util._move(test_file, self.test_user_share, self.test_local_share)
        self.assertFalse(
            self.test_user_share.joinpath("bar").exists(), "bar did not move from src"
        )
        self.assertTrue(
            self.test_local_share.joinpath("bar").exists(), "bar did not move to dst"
        )

        # Link
        umu_util._move(
            self.test_user_share.joinpath("qux"),
            self.test_user_share,
            self.test_local_share,
        )
        self.assertFalse(
            self.test_user_share.joinpath("qux").is_symlink(),
            "qux did not move from src",
        )
        self.assertTrue(
            self.test_local_share.joinpath("qux").is_symlink(),
            "qux did not move to dst",
        )

    def test_ge_proton(self):
        """Test check_env when the code name GE-Proton is set for PROTONPATH.

        Tests the case when the user has no internet connection or GE-Proton
        wasn't found in local system.
        """
        test_archive = self.test_archive.rename("GE-Proton9-2.tar.gz")
        umu_dl_util._extract_dir(test_archive, self.test_compat)

        with (
            self.assertRaises(FileNotFoundError),
            patch.object(umu_dl_util, "_fetch_releases", return_value=None),
            patch.object(umu_dl_util, "_get_latest", return_value=None),
            patch.object(umu_dl_util, "_get_from_steamcompat", return_value=None),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["PROTONPATH"] = "GE-Proton"
            umu_run.check_env(self.env)
            self.assertEqual(
                self.env["PROTONPATH"],
                self.test_compat.joinpath(
                    self.test_archive.name[: self.test_archive.name.find(".tar.gz")]
                ).as_posix(),
                "Expected PROTONPATH to be proton dir in compat",
            )

        test_archive.unlink()

    def test_ge_proton_none(self):
        """Test check_env when the code name GE-Proton is set for PROTONPATH.

        Tests the case when the user has no internet connection or GE-Proton
        wasn't found in local system.
        """
        with (
            self.assertRaises(FileNotFoundError),
            patch.object(umu_dl_util, "_fetch_releases", return_value=None),
            patch.object(umu_dl_util, "_get_latest", return_value=None),
            patch.object(umu_dl_util, "_get_from_steamcompat", return_value=None),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["PROTONPATH"] = "GE-Proton"
            umu_run.check_env(self.env)
            self.assertFalse(os.environ.get("PROTONPATH"), "Expected empty string")

    def test_update_umu_empty(self):
        """Test _update_umu by mocking an update to the runtime tools.

        When files are missing, re-copy the directory and without removing
        NOTE: This depends on umu_version.json to exist
        """
        result = None
        json_local = None
        json_root = umu_util._get_json(self.test_user_share, "umu_version.json")
        # Mock an update-to-date config file
        config = {
            "umu": {
                "versions": {
                    "launcher": "0.1-RC3",
                    "runner": "0.1-RC3",
                    "runtime_platform": "sniper_platform_0.20240125.75305",
                    "reaper": "1.0",
                    "pressure_vessel": "v0.20240212.0",
                }
            }
        }
        data = json.dumps(config, indent=4)

        # Do not mock the tools in .local/share/umu
        # Leave all of the tool dirs missing except the config

        # Config
        self.test_local_share.joinpath("umu_version.json").touch()
        with self.test_local_share.joinpath("umu_version.json").open(mode="w") as file:
            file.write(data)
        json_local = umu_util._get_json(self.test_local_share, "umu_version.json")

        self.assertTrue(
            self.test_local_share.joinpath("umu_version.json").is_file(),
            "Expected umu_version.json to be in local share",
        )

        # Update
        with (
            patch.object(umu_util, "setup_runtime", return_value=None),
        ):
            result = umu_util._update_umu(
                self.test_local_share,
                json_root,
                json_local,
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(Path(self.test_user_share, "run"), Path(self.test_local_share, "run"))
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "umu"),
                Path(self.test_local_share, "umu"),
            )
            copytree(
                Path(self.test_user_share, "pressure-vessel"),
                Path(self.test_local_share, "pressure-vessel"),
                dirs_exist_ok=True,
                symlinks=True,
            )

        self.assertFalse(result, "Expected None when calling _update_umu")

        # Now, check the state of .local/share/umu
        # We expect the relevant files to be restored

        # Check if the configuration files are equal
        # We update this on every update of the tools
        with self.test_user_share.joinpath("umu_version.json").open(mode="rb") as file1:
            root = file1.read()
            local = b""
            with self.test_local_share.joinpath("umu_version.json").open(
                mode="rb"
            ) as file2:
                local = file2.read()
            self.assertEqual(
                hashlib.blake2b(root).digest(),
                hashlib.blake2b(local).digest(),
                "Expected configuration files to be the same",
            )

        # Runtime Platform
        self.assertTrue(
            self.test_local_share.joinpath(
                json_local["umu"]["versions"]["runtime_platform"]
            ).is_dir(),
            "Expected runtime to in local share",
        )

        # Pressure Vessel
        self.assertTrue(
            self.test_local_share.joinpath("pressure-vessel").is_dir(),
            "Expected pressure vessel to in local share",
        )

    def test_update_umu(self):
        """Test _update_umu by mocking an update to the runtime tools.

        We test the existing install case.

        NOTE: This is **very** important as the update process involves
        replacing directories.
        While the directory we're removing is ours, we do **not** want
        unintended removals
        """
        result = None
        json_local = None
        json_root = umu_util._get_json(self.test_user_share, "umu_version.json")
        rt_files = [
            "run",
            "run-in-sniper",
            "umu",
        ]
        # Mock an outdated umu_version.json in ~/.local/share/umu
        # Downgrade these files: launcher, runner, runtime_platform, reaper
        # We don't downgrade Pressure Vessel because it's a runtime property
        config = {
            "umu": {
                "versions": {
                    "launcher": "0.1-RC2",
                    "runner": "0.1-RC2",
                    "runtime_platform": "sniper_platform_0.20240125.75304",
                    "reaper": "0.1",
                    "pressure_vessel": "v0.20240212.0",
                }
            }
        }
        data = json.dumps(config, indent=4)

        # In .local/share/umu we expect at least these files to exist:
        # +-- umu (root directory)
        # |   +-- pressure-vessel                               (directory)
        # |   +-- *_platform_0.20240125.75304                   (directory)
        # |   +-- run                                           (normal file)
        # |   +-- run-in-*                                      (normal file)
        # |   +-- umu                                         (normal file)
        # |   +-- umu_version.json                            (normal file)
        #
        # To test for potential unintended removals in that dir and that a
        # selective update is performed, additional files will be added to the top-level
        # After an update, those files should still exist and the count should
        # be: count_user_share_files - num_test_files + num_foo_files

        # Add foo files to top-level
        self.test_local_share.joinpath("foo").touch()
        self.test_local_share.joinpath("bar").touch()
        self.test_local_share.joinpath("baz").touch()

        # Do the same for compatibilitytools.d as we do **not** want to
        # unintentionally remove the user's Proton directory
        self.test_compat.joinpath("GE-Proton-foo").mkdir()

        # Config
        self.test_local_share.joinpath("umu_version.json").touch()
        with self.test_local_share.joinpath("umu_version.json").open(mode="w") as file:
            file.write(data)
        json_local = umu_util._get_json(self.test_local_share, "umu_version.json")

        self.assertTrue(
            self.test_local_share.joinpath("umu_version.json").is_file(),
            "Expected umu_version.json to be in local share",
        )

        # Mock the runtime files
        self.test_local_share.joinpath(
            json_local["umu"]["versions"]["runtime_platform"]
        ).mkdir()
        self.test_local_share.joinpath(
            json_local["umu"]["versions"]["runtime_platform"], "bar"
        ).touch()
        for file in rt_files:
            with self.test_local_share.joinpath(file).open(mode="w") as filer:
                filer.write("foo")

        # Mock pressure vessel
        self.test_local_share.joinpath("pressure-vessel").mkdir()
        self.test_local_share.joinpath("pressure-vessel", "bar").touch()

        # Update
        with (
            patch.object(umu_util, "setup_runtime", return_value=None),
        ):
            result = umu_util._update_umu(
                self.test_local_share,
                json_root,
                json_local,
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(Path(self.test_user_share, "run"), Path(self.test_local_share, "run"))
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "umu"),
                Path(self.test_local_share, "umu"),
            )
            copytree(
                Path(self.test_user_share, "pressure-vessel"),
                Path(self.test_local_share, "pressure-vessel"),
                dirs_exist_ok=True,
                symlinks=True,
            )

        self.assertFalse(result, "Expected None when calling _update_umu")

        # Check that foo files still exist after the update
        self.assertTrue(
            self.test_local_share.joinpath("foo").is_file(),
            "Expected test file to survive after update",
        )
        self.assertTrue(
            self.test_local_share.joinpath("bar").is_file(),
            "Expected test file to survive after update",
        )
        self.assertTrue(
            self.test_local_share.joinpath("baz").is_file(),
            "Expected test file to survive after update",
        )

        # Check that foo Proton still exists after the update
        self.assertTrue(
            self.test_compat.joinpath("GE-Proton-foo").is_dir(),
            "Expected test Proton to survive after update",
        )

        # Check if the configuration files are equal because we update this on
        # every update of the tools
        with self.test_user_share.joinpath("umu_version.json").open(mode="rb") as file1:
            root = file1.read()
            local = b""
            with self.test_local_share.joinpath("umu_version.json").open(
                mode="rb"
            ) as file2:
                local = file2.read()
            self.assertEqual(
                hashlib.blake2b(root).digest(),
                hashlib.blake2b(local).digest(),
                "Expected configuration files to be the same",
            )

        # Runtime Platform
        self.assertTrue(
            self.test_local_share.joinpath(
                json_local["umu"]["versions"]["runtime_platform"]
            ).is_dir(),
            "Expected runtime to in local share",
        )

        # Pressure Vessel
        self.assertTrue(
            self.test_local_share.joinpath("pressure-vessel").is_dir(),
            "Expected pressure vessel to in local share",
        )

    def test_install_umu(self):
        """Test _install_umu by mocking a first launch.

        At first launch, the directory /usr/share/umu is expected to be
        populated by distribution's package manager

        This function is expected to be run when ~/.local/share/umu is empty

        The contents of ~/.local/share/umu should be nearly identical to
        /usr/share/umu, with the exception of the umu-launcher files

        umu-launcher is expected to be copied to compatibilitytools.d
        """
        result = None
        json = umu_util._get_json(self.test_user_share, "umu_version.json")

        # Mock setting up the runtime
        # In the real usage, we callout to acquire the archive and
        # extract to .local/share/umu
        with (
            patch.object(umu_util, "setup_runtime", return_value=None),
        ):
            result = umu_util._install_umu(
                self.test_user_share, self.test_local_share, json
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(Path(self.test_user_share, "run"), Path(self.test_local_share, "run"))
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "umu"),
                Path(self.test_local_share, "umu"),
            )

        # Verify the state of the local share directory
        self.assertFalse(result, "Expected None after calling _install_umu")

        # Config
        self.assertTrue(
            Path(self.test_user_share, "umu_version.json").is_file(),
            "Expected umu_version.json to exist",
        )

        # Pressure Vessel
        self.assertTrue(
            Path(self.test_user_share, "pressure-vessel").is_dir(),
            "Expected pressure vessel to exist",
        )
        self.assertTrue(
            Path(self.test_user_share, "pressure-vessel", "foo").is_file(),
            "Expected foo to exist in Pressure Vessel dir",
        )

        # Runtime
        self.assertTrue(
            Path(self.test_local_share, "sniper_platform_0.20240125.75305").is_dir(),
            "Expected runtime to exist",
        )
        self.assertTrue(
            Path(
                self.test_local_share, "sniper_platform_0.20240125.75305", "foo"
            ).is_file(),
            "Expected foo to exist in runtime",
        )
        self.assertTrue(
            Path(self.test_local_share, "run").is_file(), "Expected run to exist"
        )
        self.assertTrue(
            Path(self.test_local_share, "run-in-sniper").is_file(),
            "Expected other run to exist",
        )
        self.assertTrue(
            Path(self.test_local_share, "umu").is_file(), "Expected umu to exist"
        )

    def test_get_json_err(self):
        """Test _get_json when specifying a corrupted umu_version.json file.

        A ValueError should be raised because we expect 'umu' and 'version'
        keys to exist
        """
        test_config = """
        {
            "foo": {
                "versions": {
                    "launcher": "0.1-RC3",
                    "runner": "0.1-RC3",
                    "runtime_platform": "sniper_platform_0.20240125.75305",
                    "reaper": "1.0",
                    "pressure_vessel": "v0.20240212.0"
                }
            }
        }
        """
        test_config2 = """
        {
            "umu": {
                "foo": {
                    "launcher": "0.1-RC3",
                    "runner": "0.1-RC3",
                    "runtime_platform": "sniper_platform_0.20240125.75305",
                    "reaper": "1.0",
                    "pressure_vessel": "v0.20240212.0"
                }
            }
        }
        """
        # Remove the valid config created at setup
        Path(self.test_user_share, "umu_version.json").unlink(missing_ok=True)

        Path(self.test_user_share, "umu_version.json").touch()
        with Path(self.test_user_share, "umu_version.json").open(
            mode="w", encoding="utf-8"
        ) as file:
            file.write(test_config)

        # Test when "umu" doesn't exist
        with self.assertRaisesRegex(ValueError, "load"):
            umu_util._get_json(self.test_user_share, "umu_version.json")

        # Test when "versions" doesn't exist
        Path(self.test_user_share, "umu_version.json").unlink(missing_ok=True)

        Path(self.test_user_share, "umu_version.json").touch()
        with Path(self.test_user_share, "umu_version.json").open(
            mode="w", encoding="utf-8"
        ) as file:
            file.write(test_config2)

        with self.assertRaisesRegex(ValueError, "load"):
            umu_util._get_json(self.test_user_share, "umu_version.json")

    def test_get_json_foo(self):
        """Test _get_json when not specifying umu_version.json as 2nd arg.

        A FileNotFoundError should be raised
        """
        with self.assertRaisesRegex(FileNotFoundError, "configuration"):
            umu_util._get_json(self.test_user_share, "foo")

    def test_get_json(self):
        """Test _get_json.

        This function is used to verify the existence and integrity of
        umu_version.json file during the setup process

        umu_version.json is used to synchronize the state of 2 directories:
        /usr/share/umu and ~/.local/share/umu

        An error should not be raised when passed a JSON we expect
        """
        result = None

        self.assertTrue(
            self.test_user_share.joinpath("umu_version.json").exists(),
            "Expected umu_version.json to exist",
        )

        result = umu_util._get_json(self.test_user_share, "umu_version.json")
        self.assertIsInstance(result, dict, "Expected a dict")

    def test_latest_interrupt(self):
        """Test _get_latest when the user interrupts the download/extraction.

        Assumes a file is being downloaded or extracted in this case

        A KeyboardInterrupt should be raised, and the cache/compat dir should
        be cleaned afterwards
        """
        result = None
        # In the real usage, should be populated after successful callout
        # for latest Proton releases
        # In this case, assume the test variable will be downloaded
        files = [("", ""), (self.test_archive.name, "")]

        with patch("umu_dl_util._fetch_proton") as mock_function:
            # Mock the interrupt
            # We want the dir we tried to extract to be cleaned
            mock_function.side_effect = KeyboardInterrupt
            result = umu_dl_util._get_latest(
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
        """Test _get_latest when something goes wrong when downloading Proton.

        Assumes a file is being downloaded in this case

        A ValueError should be raised, and one case it can happen is if the
        digests mismatched for some reason
        """
        result = None
        # In the real usage, should be populated after successful callout for
        # latest Proton releases
        # When empty, it means the callout failed for some reason (e.g. no internet)
        files = [("", ""), (self.test_archive.name, "")]

        self.assertTrue(
            self.test_archive.is_file(),
            "Expected test file in cache to exist",
        )

        with patch("umu_dl_util._fetch_proton") as mock_function:
            # Mock the interrupt
            mock_function.side_effect = ValueError
            result = umu_dl_util._get_latest(
                self.env, self.test_compat, self.test_cache, files
            )
            self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to be empty")
            self.assertFalse(result, "Expected None when a ValueError occurs")

            # Ensure we clean up suspected files
            self.assertFalse(
                self.test_archive.is_file(),
                "Expected test file in cache to be deleted",
            )

    def test_latest_offline(self):
        """Test _get_latest when the user doesn't have internet."""
        result = None
        # In the real usage, should be populated after successful callout for
        # latest Proton releases
        # When empty, it means the callout failed for some reason (e.g. no internet)
        files = []

        os.environ["PROTONPATH"] = ""

        with patch("umu_dl_util._fetch_proton"):
            result = umu_dl_util._get_latest(
                self.env, self.test_compat, self.test_cache, files
            )
            self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to be empty")
            self.assertFalse(result, "Expected None to be returned from _get_latest")

    def test_link_umu(self):
        """Test __get_latest for recreating the UMU-Latest link.

        This link should always be recreated to ensure clients can reliably
        kill the wineserver process for the current prefix

        In the real usage, this will fail if the user already has a UMU-Latest
        directory for some reason or the link somehow gets deleted after it
        gets recreated by the launcher
        """
        result = None
        latest = Path("UMU-Proton-9.0-beta15")
        latest.mkdir()
        Path(f"{latest}.sha512sum").touch()
        files = [(f"{latest}.sha512sum", ""), (f"{latest}.tar.gz", "")]

        # Mock the latest Proton in /tmp
        test_archive = self.test_cache.joinpath(f"{latest}.tar.gz")
        with tarfile.open(test_archive.as_posix(), "w:gz") as tar:
            tar.add(latest.as_posix(), arcname=latest.as_posix())

        # UMU-Latest will not exist in this installation
        self.test_compat.joinpath("UMU-Proton-9.0-beta15").mkdir()

        os.environ["PROTONPATH"] = ""

        self.assertFalse(
            self.test_compat.joinpath("UMU-Latest").exists(),
            "Expected UMU-Latest link to not exist",
        )
        with (
            patch("umu_dl_util._fetch_proton"),
        ):
            result = umu_dl_util._get_latest(
                self.env, self.test_compat, self.test_cache, files
            )
            self.assertTrue(result is self.env, "Expected the same reference")
            # Verify the latest was set
            self.assertEqual(
                self.env.get("PROTONPATH"),
                self.test_compat.joinpath(latest).as_posix(),
                "Expected latest to be set",
            )
            self.assertTrue(
                self.test_compat.joinpath("UMU-Latest").is_symlink(),
                "Expected UMU-Latest symlink",
            )
            # Verify link
            self.assertEqual(
                self.test_compat.joinpath("UMU-Latest").readlink(),
                latest,
                f"Expected UMU-Latest link to be ./{latest}",
            )

        latest.rmdir()
        Path(f"{latest}.sha512sum").unlink()

    def test_latest_umu(self):
        """Test _get_latest when online and when an empty PROTONPATH is set.

        Tests that the latest UMU-Proton was set to PROTONPATH and old
        stable versions were removed in the process.
        """
        result = None
        latest = Path("UMU-Proton-9.0-beta16")
        latest.mkdir()
        Path(f"{latest}.sha512sum").touch()
        files = [(f"{latest}.sha512sum", ""), (f"{latest}.tar.gz", "")]

        # Mock the latest Proton in /tmp
        test_archive = self.test_cache.joinpath(f"{latest}.tar.gz")
        with tarfile.open(test_archive.as_posix(), "w:gz") as tar:
            tar.add(latest.as_posix(), arcname=latest.as_posix())

        # Mock old versions
        self.test_compat.joinpath("UMU-Proton-9.0-beta15").mkdir()
        self.test_compat.joinpath("UMU-Proton-9.0-beta14").mkdir()
        self.test_compat.joinpath("ULWGL-Proton-8.0-5-2").mkdir()

        # Create foo files and GE-Proton. We do *not* want unintended
        # removals
        self.test_compat.joinpath("foo").mkdir()
        self.test_compat.joinpath("GE-Proton9-2").mkdir()

        os.environ["PROTONPATH"] = ""

        with (
            patch("umu_dl_util._fetch_proton"),
        ):
            result = umu_dl_util._get_latest(
                self.env, self.test_compat, self.test_cache, files
            )
            self.assertTrue(result is self.env, "Expected the same reference")
            # Verify the latest was set
            self.assertEqual(
                self.env.get("PROTONPATH"),
                self.test_compat.joinpath(latest).as_posix(),
                "Expected latest to be set",
            )
            # Verify that the old versions were deleted
            self.assertFalse(
                self.test_compat.joinpath("UMU-Proton-9.0-beta15").exists(),
                "Expected old version to be removed",
            )
            self.assertFalse(
                self.test_compat.joinpath("UMU-Proton-9.0-beta14").exists(),
                "Expected old version to be removed",
            )
            self.assertFalse(
                self.test_compat.joinpath("ULWGL-Proton-8.0-5-2").exists(),
                "Expected old version to be removed",
            )
            # Verify foo files survived
            self.assertTrue(
                self.test_compat.joinpath("foo").exists(), "Expected foo to survive"
            )
            self.assertTrue(
                self.test_compat.joinpath("GE-Proton9-2").exists(),
                "Expected GE-Proton9-2 to survive",
            )
            self.assertTrue(
                self.test_compat.joinpath("UMU-Latest").is_symlink(),
                "Expected UMU-Latest symlink",
            )
            # Verify link
            self.assertEqual(
                self.test_compat.joinpath("UMU-Latest").readlink(),
                latest,
                f"Expected UMU-Latest link to be ./{latest}",
            )

        latest.rmdir()
        Path(f"{latest}.sha512sum").unlink()

    def test_steamcompat_nodir(self):
        """Test _get_from_steamcompat when Proton doesn't exist in compat dir.

        In this case, None should be returned to signal that we should
        continue with downloading the latest Proton
        """
        result = None

        result = umu_dl_util._get_from_steamcompat(self.env, self.test_compat)

        self.assertFalse(result, "Expected None after calling _get_from_steamcompat")
        self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to not be set")

    def test_steamcompat(self):
        """Test _get_from_steamcompat.

        When a Proton exist in .local/share/Steam/compatibilitytools.d, use it
        when PROTONPATH is unset
        """
        result = None

        umu_dl_util._extract_dir(self.test_archive, self.test_compat)

        result = umu_dl_util._get_from_steamcompat(self.env, self.test_compat)

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

        In the event of an interrupt during the download/extract process, we
        only want to clean the files that exist

        NOTE: This is **extremely** important, as we do **not** want to delete
        anything else but the files we downloaded/extracted -- the incomplete
        tarball/extracted dir
        """
        result = None

        umu_dl_util._extract_dir(self.test_archive, self.test_compat)

        # Create a file in the cache and compat
        self.test_cache.joinpath("foo").touch()
        self.test_compat.joinpath("foo").touch()

        # Before cleaning
        # On setUp, an archive is created and a dir should exist in compat
        # after extraction
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
        result = umu_dl_util._cleanup(
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

        In the event of an interrupt during the download/extract process, we
        want to clean the cache or the extracted dir in Steam compat to avoid
        incomplete files
        """
        result = None

        umu_dl_util._extract_dir(self.test_archive, self.test_compat)
        result = umu_dl_util._cleanup(
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

        A ReadError should be raised as we only expect .tar.gz releases
        """
        test_archive = self.test_cache.joinpath(f"{self.test_proton_dir}.tar")
        # Do not apply compression
        with tarfile.open(test_archive.as_posix(), "w") as tar:
            tar.add(
                self.test_proton_dir.as_posix(), arcname=self.test_proton_dir.as_posix()
            )

        with self.assertRaisesRegex(tarfile.ReadError, "gzip"):
            umu_dl_util._extract_dir(test_archive, self.test_compat)

        if test_archive.exists():
            test_archive.unlink()

    def test_extract(self):
        """Test _extract_dir.

        An error should not be raised when the Proton release is extracted to
        the Steam compat dir
        """
        result = None

        result = umu_dl_util._extract_dir(self.test_archive, self.test_compat)
        self.assertFalse(result, "Expected None after extracting")
        self.assertTrue(
            self.test_compat.joinpath(self.test_proton_dir).exists(),
            "Expected proton dir to exists in compat",
        )
        self.assertTrue(
            self.test_compat.joinpath(self.test_proton_dir).joinpath("proton").exists(),
            "Expected 'proton' file to exists in the proton dir",
        )

    def test_game_drive_libpath_empty(self):
        """Test enable_steam_game_drive when LD_LIBRARY_PATH is empty.

        Distributions or GUI launchers may set the LD_LIBRARY_PATH environment
        variable to reference their own runtime library paths. In the case for
        Flatpaks, if this variable is not declared and set with paths in the
        manifest then it's observed that the default is an empty string. As a
        result, the current working directory will be added to the
        STEAM_RUNTIME_LIBRARY_PATH result.
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
            args = umu_run.parse_args()
            # Config
            umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            umu_run.set_env(self.env, args)

            if "LD_LIBRARY_PATH" in os.environ:
                os.environ.pop("LD_LIBRARY_PATH")

            # Flatpak defaults to an empty string
            paths = ""
            os.environ["LD_LIBRARY_PATH"] = paths

            # Game drive
            result_gamedrive = umu_run.enable_steam_game_drive(self.env)

        for key, val in self.env.items():
            os.environ[key] = val

        # Game drive
        self.assertTrue(result_gamedrive is self.env, "Expected the same reference")
        self.assertTrue(
            self.env["STEAM_RUNTIME_LIBRARY_PATH"],
            "Expected two elements in STEAM_RUNTIME_LIBRARY_PATHS",
        )

        # Expect LD_LIBRARY_PATH was added ontop of /usr/lib and /usr/lib64
        self.assertEqual(
            len(self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":")),
            2,
            "Expected two values in STEAM_RUNTIME_LIBRARY_PATH",
        )

        # An error should be raised if /usr/lib or /usr/lib64 is found twice
        lib_paths = set()
        for path in self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":"):
            if path not in lib_paths:
                lib_paths.add(path)
            elif path in lib_paths:
                err: str = f"Duplicate path found in STEAM_RUNTIME_LIBRARY_PATH: {path}"
                raise AssertionError(err)

        # Both of these values should be empty still after calling
        # enable_steam_game_drive
        self.assertFalse(
            self.env["STEAM_COMPAT_INSTALL_PATH"],
            "Expected STEAM_COMPAT_INSTALL_PATH to be empty when passing an empty EXE",
        )
        self.assertFalse(self.env["EXE"], "Expected EXE to be empty on empty string")

    def test_game_drive_libpath(self):
        """Test enable_steam_game_drive for duplicate paths.

        Distributions or GUI launchers may set the LD_LIBRARY_PATH environment
        variable to reference their own runtime library paths. Ensure that
        there will never be duplicates in that environment variable.
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
            args = umu_run.parse_args()
            # Config
            umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            umu_run.set_env(self.env, args)

            if "LD_LIBRARY_PATH" in os.environ:
                os.environ.pop("LD_LIBRARY_PATH")

            # Mock Lutris's LD_LIBRARY_PATH
            paths = (
                "/home/foo/.local/share/lutris/runtime/steam/i386/usr/lib:"
                "/usr/lib:"
                "/usr/lib32:"
                "/usr/lib64:"
                "/home/foo/.local/share/lutris/runtime/steam/amd64/lib:"
                "/home/foo/.local/share/lutris/runtime/steam/amd64/usr/lib:"
                "/home/foo/.local/share/lutris/runtime/Ubuntu-18.04-i686:"
                "/home/foo/.local/share/lutris/runtime/steam/i386/lib:"
                "/usr/lib/libfakeroot:"
                "/home/foo/.local/share/lutris/runtime/steam/amd64/lib/x86_64-linux-gnu:"
                "/home/foo/.local/share/lutris/runtime/steam/i386/usr/lib/i386-linux-gnu:"
                "/home/foo/.local/share/lutris/runtime/Ubuntu-18.04-x86_64:"
                "/home/foo/.local/share/lutris/runtime/steam/i386/lib/i386-linux-gnu:"
                "/home/foo/.local/share/lutris/runtime/steam/amd64/usr/lib/x86_64-linux-gnu"
            )
            os.environ["LD_LIBRARY_PATH"] = paths

            # Game drive
            result_gamedrive = umu_run.enable_steam_game_drive(self.env)

        for key, val in self.env.items():
            os.environ[key] = val

        # Game drive
        self.assertTrue(result_gamedrive is self.env, "Expected the same reference")
        self.assertTrue(
            self.env["STEAM_RUNTIME_LIBRARY_PATH"],
            "Expected two elements in STEAM_RUNTIME_LIBRARY_PATHS",
        )

        # Expect LD_LIBRARY_PATH was added ontop of /usr/lib and /usr/lib64
        self.assertNotEqual(
            len(self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":")),
            2,
            "Expected more than two values in STEAM_RUNTIME_LIBRARY_PATH",
        )

        # An error should be raised if /usr/lib or /usr/lib64 is found twice
        lib_paths = set()
        for path in self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":"):
            if path not in lib_paths:
                lib_paths.add(path)
            elif path in lib_paths:
                err: str = f"Duplicate path found in STEAM_RUNTIME_LIBRARY_PATH: {path}"
                raise AssertionError(err)

        # Both of these values should be empty still after calling
        # enable_steam_game_drive
        self.assertFalse(
            self.env["STEAM_COMPAT_INSTALL_PATH"],
            "Expected STEAM_COMPAT_INSTALL_PATH to be empty when passing an empty EXE",
        )
        self.assertFalse(self.env["EXE"], "Expected EXE to be empty on empty string")

    def test_game_drive_empty(self):
        """Test enable_steam_game_drive.

        WINE prefixes can be created by passing an empty string
        Example:
        WINEPREFIX= PROTONPATH= GAMEID= umu-run ""

        During this process, we attempt to prepare setting up game drive and
        set the values for STEAM_RUNTIME_LIBRARY_PATH and
        STEAM_COMPAT_INSTALL_PATHS

        The resulting value of those variables should be colon delimited
        string with no leading colons and contain only /usr/lib or /usr/lib32

        Ignores LD_LIBRARY_PATH, relevant to Game Drive, which is sourced in
        Ubuntu and maybe its derivatives
        """
        args = None
        result_gamedrive = None
        # Expected library paths for the container runtime framework
        libpaths = {
            "/usr/lib64",
            "/usr/lib32",
            "/usr/lib",
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib/i386-linux-gnu",
        }
        Path(self.test_file + "/proton").touch()

        # Replicate main's execution and test up until enable_steam_game_drive
        with patch("sys.argv", ["", ""]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            # Args
            args = umu_run.parse_args()
            # Config
            umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            umu_run.set_env(self.env, args)

            # Some distributions source this variable (e.g. Ubuntu) and will
            # be added to the result of STEAM_RUNTIME_LIBRARY_PATH
            # Only test the case without it set
            if "LD_LIBRARY_PATH" in os.environ:
                os.environ.pop("LD_LIBRARY_PATH")

            # Game drive
            result_gamedrive = umu_run.enable_steam_game_drive(self.env)

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

        # Check that there are no trailing colons, unexpected characters
        # and is officially supported
        str1, str2 = self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":")
        self.assertTrue(str1 in libpaths, f"Expected a path in: {libpaths}")
        self.assertTrue(str2 in libpaths, f"Expected a path in: {libpaths}")

        # Both of these values should be empty still after calling
        # enable_steam_game_drive
        self.assertFalse(
            self.env["STEAM_COMPAT_INSTALL_PATH"],
            "Expected STEAM_COMPAT_INSTALL_PATH to be empty when passing an empty EXE",
        )
        self.assertFalse(self.env["EXE"], "Expected EXE to be empty on empty string")

    def test_build_command(self):
        """Test build command.

        After parsing valid environment variables set by the user, be sure we
        do not raise a FileNotFoundError

        A FileNotFoundError will only be raised if the _v2-entry-point (umu)
        is not in $HOME/.local/share/umu
        """
        result_args = None
        test_command = []

        # Mock the proton file
        Path(self.test_file, "proton").touch()

        with patch("sys.argv", ["", self.test_exe]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            # Args
            result_args = umu_run.parse_args()
            # Config
            umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            umu_run.set_env(self.env, result_args)
            # Game drive
            umu_run.enable_steam_game_drive(self.env)

        for key, val in self.env.items():
            os.environ[key] = val

        # Mock setting up the runtime
        with (
            patch.object(umu_util, "setup_runtime", return_value=None),
        ):
            umu_util._install_umu(self.test_user_share, self.test_local_share, json)
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(Path(self.test_user_share, "run"), Path(self.test_local_share, "run"))
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "umu"),
                Path(self.test_local_share, "umu"),
            )

        # Build
        test_command = umu_run.build_command(
            self.env, self.test_local_share, self.test_user_share, test_command
        )
        self.assertIsInstance(test_command, list, "Expected a List from build_command")
        self.assertEqual(
            len(test_command), 10, "Expected 10 elements in the list from build_command"
        )
        reaper, id, opt0, entry_point, opt1, verb, opt2, proton, verb2, exe = [
            *test_command
        ]
        # The entry point dest could change. Just check if there's a value
        self.assertTrue(reaper, "Expected reaper")
        self.assertTrue(id, "Expected a tag for reaper")
        self.assertTrue(opt0, "Expected --")
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

        # Replicate the command:
        # WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= umu_run ...
        with patch("sys.argv", ["", self.test_exe, test_str]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = test_str
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            # Args
            result = umu_run.parse_args()
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
            umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(self.env["WINEPREFIX"])

            # Env
            # Confirm that non-normalized paths were passed before setting environment
            # The client will pass paths to WINEPREFIX, PROTONPATH and EXE
            self.assertNotEqual(
                Path(self.test_exe),
                Path(self.test_exe).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertNotEqual(
                Path(os.environ["WINEPREFIX"]),
                Path(os.environ["WINEPREFIX"]).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertNotEqual(
                Path(os.environ["PROTONPATH"]),
                Path(os.environ["PROTONPATH"]).resolve(),
                "Expected path to exe to be non-normalized",
            )
            result = umu_run.set_env(self.env, result[0:])
            self.assertTrue(result is self.env, "Expected the same reference")

            path_exe = Path(self.test_exe).expanduser().resolve().as_posix()
            path_file = Path(self.test_file).expanduser().resolve().as_posix()

            # After calling set_env all paths should be expanded POSIX form
            self.assertEqual(
                self.env["EXE"], path_exe, "Expected EXE to be normalized and expanded"
            )
            self.assertEqual(self.env["STORE"], test_str, "Expected STORE to be set")
            self.assertEqual(
                self.env["PROTONPATH"],
                path_file,
                "Expected PROTONPATH to be normalized and expanded",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                path_file,
                "Expected WINEPREFIX to be normalized and expanded",
            )
            self.assertEqual(self.env["GAMEID"], test_str, "Expected GAMEID to be set")
            self.assertEqual(
                self.env["PROTON_VERB"],
                self.test_verb,
                "Expected PROTON_VERB to be set",
            )

    def test_set_env_id(self):
        """Test set_env.

        Verify that environment variables (dictionary) are set after calling
        set_env when passing a valid UMU_ID

        When a valid UMU_ID is set, the STEAM_COMPAT_APP_ID variables
        should be the stripped UMU_ID
        """
        result = None
        test_str = "foo"
        umu_id = "umu-271590"

        # Replicate the usage:
        # WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= umu_run ...
        with patch("sys.argv", ["", self.test_exe]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = umu_id
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            # Args
            result = umu_run.parse_args()
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
            umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            result = umu_run.set_env(self.env, result[0:])
            self.assertTrue(result is self.env, "Expected the same reference")

            path_exe = Path(self.test_exe).expanduser().resolve().as_posix()
            path_file = Path(self.test_file).expanduser().resolve().as_posix()

            # After calling set_env all paths should be expanded POSIX form
            self.assertEqual(
                self.env["EXE"],
                path_exe,
                "Expected EXE to be normalized and expanded",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_INSTALL_PATH"],
                Path(path_exe).parent.as_posix(),
                "Expected STEAM_COMPAT_INSTALL_PATH to be set",
            )
            self.assertEqual(self.env["STORE"], test_str, "Expected STORE to be set")
            self.assertEqual(
                self.env["PROTONPATH"],
                path_file,
                "Expected PROTONPATH to be normalized and expanded",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                path_file,
                "Expected WINEPREFIX to be normalized and expanded",
            )
            self.assertEqual(self.env["GAMEID"], umu_id, "Expected GAMEID to be set")
            self.assertEqual(
                self.env["PROTON_VERB"],
                self.test_verb,
                "Expected PROTON_VERB to be set",
            )
            # umu
            self.assertEqual(
                self.env["UMU_ID"],
                self.env["GAMEID"],
                "Expected UMU_ID to be GAMEID",
            )
            self.assertEqual(self.env["UMU_ID"], umu_id, "Expected UMU_ID")
            # Should be stripped -- everything after the hyphen
            self.assertEqual(
                self.env["STEAM_COMPAT_APP_ID"],
                umu_id[umu_id.find("-") + 1 :],
                "Expected STEAM_COMPAT_APP_ID to be the stripped UMU_ID",
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
                self.env["PROTONPATH"]
                + ":"
                + Path.home().joinpath(".local", "share", "umu").as_posix(),
                "Expected STEAM_COMPAT_TOOL_PATHS to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_MOUNTS"],
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                "Expected STEAM_COMPAT_MOUNTS to be set",
            )

    def test_set_env_exe(self):
        """Test set_env when the executable fails to be resolved.

        A FileNotFoundError should be raised and handled. Afterwards, the launcher will
        assume that the executable exists inside the WINE prefix or container
        (e.g., winecfg)
        """
        result = None
        test_str = "foo"

        # Replicate the usage:
        # WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= umu_run ...
        with patch("sys.argv", ["", test_str]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = test_str
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            # Args
            result = umu_run.parse_args()
            self.assertIsInstance(result, tuple, "Expected a tuple")
            self.assertIsInstance(result[1], list, "Expected a list as options")
            self.assertTrue(
                result[0] == test_str,
                "Expected EXE to be test string",
            )
            self.assertFalse(Path(result[0]).is_file(), "Expected EXE to not exist")
            self.assertFalse(
                result[1], "Expected an empty list when passing no options"
            )
            # Check
            umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            self.assertNotEqual(
                Path(self.test_exe),
                Path(self.test_exe).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertNotEqual(
                Path(os.environ["WINEPREFIX"]),
                Path(os.environ["WINEPREFIX"]).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertNotEqual(
                Path(os.environ["PROTONPATH"]),
                Path(os.environ["PROTONPATH"]).resolve(),
                "Expected path to exe to be non-normalized",
            )
            result = umu_run.set_env(self.env, result[0:])
            self.assertTrue(result is self.env, "Expected the same reference")

            path_exe = Path(test_str).as_posix()
            path_file = Path(self.test_file).expanduser().resolve().as_posix()

            # After calling set_env all paths should be expanded POSIX form
            self.assertEqual(self.env["EXE"], path_exe, "Expected EXE")
            self.assertFalse(
                self.env["STEAM_COMPAT_INSTALL_PATH"],
                "Expected STEAM_COMPAT_INSTALL_PATH to be empty",
            )
            self.assertEqual(self.env["STORE"], test_str, "Expected STORE to be set")
            self.assertEqual(
                self.env["PROTONPATH"],
                path_file,
                "Expected PROTONPATH to be normalized and expanded",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                path_file,
                "Expected WINEPREFIX to be normalized and expanded",
            )
            self.assertEqual(self.env["GAMEID"], test_str, "Expected GAMEID to be set")
            self.assertEqual(
                self.env["PROTON_VERB"],
                self.test_verb,
                "Expected PROTON_VERB to be set",
            )
            # umu
            self.assertEqual(
                self.env["UMU_ID"],
                self.env["GAMEID"],
                "Expected UMU_ID to be GAMEID",
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
                self.env["PROTONPATH"]
                + ":"
                + Path.home().joinpath(".local", "share", "umu").as_posix(),
                "Expected STEAM_COMPAT_TOOL_PATHS to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_MOUNTS"],
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                "Expected STEAM_COMPAT_MOUNTS to be set",
            )

    def test_set_env(self):
        """Test set_env.

        Verify that environment variables (dictionary) are set after calling
        set_env
        """
        result = None
        test_str = "foo"

        # Replicate the usage:
        # WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= umu_run ...
        with patch("sys.argv", ["", self.test_exe]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = test_str
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            # Args
            result = umu_run.parse_args()
            self.assertIsInstance(result, tuple, "Expected a tuple")
            self.assertIsInstance(result[0], str, "Expected a string")
            self.assertIsInstance(result[1], list, "Expected a list as options")
            self.assertEqual(
                result[0],
                "./tmp.WMYQiPb9A/foo",
                "Expected EXE to be unexpanded",
            )
            self.assertFalse(
                result[1], "Expected an empty list when passing no options"
            )
            # Check
            umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            self.assertNotEqual(
                Path(self.test_exe),
                Path(self.test_exe).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertNotEqual(
                Path(os.environ["WINEPREFIX"]),
                Path(os.environ["WINEPREFIX"]).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertNotEqual(
                Path(os.environ["PROTONPATH"]),
                Path(os.environ["PROTONPATH"]).resolve(),
                "Expected path to exe to be non-normalized",
            )
            result = umu_run.set_env(self.env, result[0:])
            self.assertTrue(result is self.env, "Expected the same reference")

            path_exe = Path(self.test_exe).expanduser().resolve().as_posix()
            path_file = Path(self.test_file).expanduser().resolve().as_posix()

            # After calling set_env all paths should be expanded POSIX form
            self.assertEqual(
                self.env["EXE"], path_exe, "Expected EXE to be normalized and expanded"
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_INSTALL_PATH"],
                Path(path_exe).parent.as_posix(),
                "Expected STEAM_COMPAT_INSTALL_PATH to be set",
            )
            self.assertEqual(self.env["STORE"], test_str, "Expected STORE to be set")
            self.assertEqual(
                self.env["PROTONPATH"],
                path_file,
                "Expected PROTONPATH to be normalized and expanded",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                path_file,
                "Expected WINEPREFIX to be normalized and expanded",
            )
            self.assertEqual(self.env["GAMEID"], test_str, "Expected GAMEID to be set")
            self.assertEqual(
                self.env["PROTON_VERB"],
                self.test_verb,
                "Expected PROTON_VERB to be set",
            )
            # umu
            self.assertEqual(
                self.env["UMU_ID"],
                self.env["GAMEID"],
                "Expected UMU_ID to be GAMEID",
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
                self.env["PROTONPATH"]
                + ":"
                + Path.home().joinpath(".local", "share", "umu").as_posix(),
                "Expected STEAM_COMPAT_TOOL_PATHS to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_MOUNTS"],
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                "Expected STEAM_COMPAT_MOUNTS to be set",
            )

    def test_setup_pfx_mv(self):
        """Test setup_pfx when moving the WINEPREFIX after creating it.

        After setting up the prefix then moving it to a different path, ensure
        that the symbolic link points to that new location
        """
        result = None
        pattern = r"^/home/[\w\d]+"  # Expects only unicode decimals and alphanumerics
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(self.test_file).cwd().joinpath(self.test_file).as_posix(),
        )
        result = umu_run.setup_pfx(unexpanded_path)

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and"
            "tracked_files file",
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

    def test_setup_pfx_symlinks_else(self):
        """Test setup_pfx in the case both steamuser and unixuser exist in some form.

        Tests the case when they are symlinks
        An error should not be raised and we should just do nothing
        """
        result = None
        pattern = r"^/home/[\w\d]+"
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(
                Path(self.test_file).cwd().as_posix() + "/" + self.test_file
            ).as_posix(),
        )

        # Create only the dir
        Path(unexpanded_path).joinpath("drive_c/users").expanduser().mkdir(
            parents=True, exist_ok=True
        )

        # Create the symlink to the test file itself
        Path(unexpanded_path).joinpath("drive_c/users").joinpath(
            self.user
        ).expanduser().symlink_to(Path(self.test_file).absolute())
        Path(unexpanded_path).joinpath("drive_c/users").joinpath(
            "steamuser"
        ).expanduser().symlink_to(Path(self.test_file).absolute())

        result = umu_run.setup_pfx(unexpanded_path)

        self.assertIsNone(
            result,
            "Expected None when calling setup_pfx",
        )

    def test_setup_pfx_symlinks_unixuser(self):
        """Test setup_pfx for symbolic link to steamuser.

        Tests the case when the steamuser dir does not exist and user dir exists
        In this case, create: steamuser -> user
        """
        result = None
        pattern = r"^/home/[\w\d]+"
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(
                Path(self.test_file).cwd().as_posix() + "/" + self.test_file
            ).as_posix(),
        )

        # Create only the user dir
        Path(unexpanded_path).joinpath("drive_c/users").joinpath(
            self.user
        ).expanduser().mkdir(parents=True, exist_ok=True)

        result = umu_run.setup_pfx(unexpanded_path)

        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and "
            "tracked_files file",
        )

        # Verify steamuser -> unix user
        self.assertTrue(
            Path(self.test_file).joinpath("drive_c/users/steamuser").is_symlink(),
            "Expected steamuser to be a symbolic link",
        )
        self.assertEqual(
            Path(self.test_file).joinpath("drive_c/users/steamuser").readlink(),
            Path(self.user),
            "Expected steamuser -> user",
        )

    def test_setup_pfx_symlinks_steamuser(self):
        """Test setup_pfx for symbolic link to wine.

        Tests the case when only steamuser exist and the user dir does not exist
        """
        result = None
        pattern = r"^/home/[\w\d]+"
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(
                Path(self.test_file).cwd().as_posix() + "/" + self.test_file
            ).as_posix(),
        )

        # Create the steamuser dir
        Path(unexpanded_path + "/drive_c/users/steamuser").expanduser().mkdir(
            parents=True, exist_ok=True
        )

        result = umu_run.setup_pfx(unexpanded_path)

        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and "
            " tracked_files file",
        )

        # Verify unixuser -> steamuser
        self.assertTrue(
            Path(self.test_file + "/drive_c/users/steamuser").is_dir(),
            "Expected steamuser to be created",
        )
        self.assertTrue(
            Path(unexpanded_path + "/drive_c/users/" + self.user)
            .expanduser()
            .is_symlink(),
            "Expected symbolic link for unixuser",
        )
        self.assertEqual(
            Path(self.test_file).joinpath(f"drive_c/users/{self.user}").readlink(),
            Path("steamuser"),
            "Expected unixuser -> steamuser",
        )

    def test_setup_pfx_symlinks(self):
        """Test setup_pfx for valid symlinks.

        Ensure that symbolic links to the WINE prefix (pfx) are always in
        expanded form when passed an unexpanded path.

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
        result = umu_run.setup_pfx(unexpanded_path)

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and "
            "tracked_files file",
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

        An error should not be raised when passing paths such as
        ~/path/to/prefix
        """
        result = None
        pattern = r"^/home/[\w\d]+"  # Expects only unicode decimals and alphanumerics
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(self.test_file).as_posix(),
        )
        result = umu_run.setup_pfx(unexpanded_path)

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and "
            "tracked_files file",
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

        # Confirm the input is a relative path
        # The path will be normalized when the launcher creates the prefix link
        self.assertNotEqual(
            Path(self.test_file),
            Path(self.test_file).resolve(),
            "Expected path to be non-normalized",
        )
        result = umu_run.setup_pfx(self.test_file)
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and "
            "tracked_files file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(), "Expected pfx to be a symlink"
        )
        # Check if the symlink is normalized when passed a relative path
        self.assertEqual(
            Path(self.test_file + "/pfx").readlink().as_posix(),
            Path(self.test_file).resolve().as_posix(),
        )
        self.assertTrue(
            Path(self.test_file + "/tracked_files").is_file(),
            "Expected tracked_files to be a file",
        )
        # For new prefixes, steamuser should exist and a user symlink
        self.assertTrue(
            Path(self.test_file + "/drive_c/users/steamuser").is_dir(),
            "Expected steamuser to be created",
        )
        self.assertTrue(
            Path(self.test_file + "/drive_c/users/" + self.user)
            .expanduser()
            .is_symlink(),
            "Expected symlink of username -> steamuser",
        )

    def test_parse_args(self):
        """Test parse_args with no options.

        There's a requirement to create an empty prefix

        A SystemExit should be raised in this case:
        ./umu_run.py
        """
        with self.assertRaises(SystemExit):
            umu_run.parse_args()

    def test_parse_args_config(self):
        """Test parse_args --config."""
        with patch.object(
            umu_run,
            "parse_args",
            return_value=argparse.Namespace(config=self.test_file),
        ):
            result = umu_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )

    def test_env_proton_nodir(self):
        """Test check_env when $PROTONPATH in the case we failed to set it.

        An FileNotFoundError should be raised when we fail to set PROTONPATH
        """
        # Mock getting the Proton
        with (
            self.assertRaises(FileNotFoundError),
            patch.object(umu_run, "get_umu_proton", return_value=self.env),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            umu_run.check_env(self.env)

    def test_env_wine_empty(self):
        """Test check_env when $WINEPREFIX is empty.

        When the WINEPREFIX is empty, the current working directory of the
        user will be used as the prefix directory which should not happen.

        An ValueError should be raised
        """
        with (
            self.assertRaises(ValueError),
        ):
            os.environ["WINEPREFIX"] = ""
            os.environ["GAMEID"] = self.test_file
            umu_run.check_env(self.env)

    def test_env_gameid_empty(self):
        """Test check_env when $GAMEID is empty.

        When the GAMEID is empty in the non-config usage, no app ids will be
        set. As a result, no fixes will be applied to the current prefix

        An ValueError should be raised
        """
        with self.assertRaises(ValueError):
            os.environ["WINEPREFIX"] = ""
            os.environ["GAMEID"] = ""
            umu_run.check_env(self.env)

    def test_env_wine_dir(self):
        """Test check_env when $WINEPREFIX is not a directory.

        When the user specifies a WINEPREFIX that doesn't exist, make the dirs
        on their behalf and set it

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

        umu_run.check_env(self.env)

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
        """Test check_env for unexpanded paths in $WINEPREFIX and $PROTONPATH."""
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
        result = umu_run.check_env(self.env)
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
        result = umu_run.check_env(self.env)
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
                umu_run,
                "get_umu_proton",
                return_value=self.env,
            ):
                os.environ["WINEPREFIX"] = self.test_file
                os.environ["GAMEID"] = self.test_file
                result = umu_run.check_env(self.env)
                self.assertTrue(result is self.env, "Expected the same reference")
                self.assertFalse(os.environ["PROTONPATH"])

    def test_env_vars_wine(self):
        """Test check_env when setting only $WINEPREFIX."""
        with self.assertRaisesRegex(ValueError, "GAMEID"):
            os.environ["WINEPREFIX"] = self.test_file
            umu_run.check_env(self.env)

    def test_env_vars_none(self):
        """Tests check_env when setting no env vars.

        GAMEID should be the only strictly required env var
        """
        with self.assertRaisesRegex(ValueError, "GAMEID"):
            umu_run.check_env(self.env)


if __name__ == "__main__":
    unittest.main()
