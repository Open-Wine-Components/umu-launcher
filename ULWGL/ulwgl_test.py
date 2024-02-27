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
import ulwgl_util
import hashlib
import errno
import json


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
        # /usr/share/ULWGL
        self.test_user_share = Path("./tmp.BXk2NnvW2m")
        # ~/.local/share/Steam/compatibilitytools.d
        self.test_local_share = Path("./tmp.aDl73CbQCP")

        # Dictionary that represents the ULWGL_VERSIONS.json
        self.root_config = {
            "ulwgl": {
                "versions": {
                    "launcher": "0.1-RC3",
                    "runner": "0.1-RC3",
                    "runtime_platform": "sniper_platform_0.20240125.75305",
                    "reaper": "1.0",
                    "pressure_vessel": "v0.20240212.0",
                }
            }
        }
        # ULWGL_VERSION.json
        self.test_config = json.dumps(self.root_config, indent=4)

        self.test_user_share.mkdir(exist_ok=True)
        self.test_local_share.mkdir(exist_ok=True)
        self.test_cache.mkdir(exist_ok=True)
        self.test_compat.mkdir(exist_ok=True)
        self.test_proton_dir.mkdir(exist_ok=True)

        # Mock a valid configuration file at /usr/share/ULWGL: tmp.BXk2NnvW2m/ULWGL_VERSION.json
        Path(self.test_user_share, "ULWGL_VERSION.json").touch()
        with Path(self.test_user_share, "ULWGL_VERSION.json").open(mode="w") as file:
            file.write(self.test_config)

        # Mock the launcher files
        Path(self.test_user_share, "ulwgl_consts.py").touch()
        Path(self.test_user_share, "ulwgl_dl_util.py").touch()
        Path(self.test_user_share, "ulwgl_log.py").touch()
        Path(self.test_user_share, "ulwgl_plugins.py").touch()
        Path(self.test_user_share, "ulwgl_run.py").touch()
        Path(self.test_user_share, "ulwgl_util.py").touch()
        Path(self.test_user_share, "ulwgl-run").symlink_to("ulwgl_run.py")

        # Mock the runtime files
        Path(self.test_user_share, "sniper_platform_0.20240125.75305").mkdir()
        Path(self.test_user_share, "sniper_platform_0.20240125.75305", "foo").touch()
        Path(self.test_user_share, "run").touch()
        Path(self.test_user_share, "run-in-sniper").touch()
        Path(self.test_user_share, "ULWGL").touch()

        # Mock pressure vessel
        Path(self.test_user_share, "pressure-vessel").mkdir()
        Path(self.test_user_share, "pressure-vessel", "foo").touch()

        # Mock ULWGL-Launcher
        Path(self.test_user_share, "ULWGL-Launcher").mkdir()
        Path(self.test_user_share, "ULWGL-Launcher", "compatibilitytool.vdf").touch()
        Path(self.test_user_share, "ULWGL-Launcher", "toolmanifest.vdf").touch()
        Path(self.test_user_share, "ULWGL-Launcher", "ulwgl-run").symlink_to(
            "../../../ulwgl-run"
        )

        # Mock Reaper
        Path(self.test_user_share, "reaper").touch()

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

        if self.test_user_share.exists():
            rmtree(self.test_user_share.as_posix())

        if self.test_local_share.exists():
            rmtree(self.test_local_share.as_posix())

    def test_update_ulwgl_empty(self):
        """Test _update_ulwgl by mocking an update to the runtime tools for missing dirs.

        In this case, we simply re-copy the directory and no removal is performed
        NOTE: This depends on ULWGL_VERSION.json to exist
        """
        result = None
        json_local = None
        json_root = ulwgl_util._get_json(self.test_user_share, "ULWGL_VERSION.json")
        # Mock an update-to-date config file
        config = {
            "ulwgl": {
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

        # Do not mock the tools in .local/share/ULWGL
        # Leave all of the tool dirs missing except the config

        # Config
        self.test_local_share.joinpath("ULWGL_VERSION.json").touch()
        with self.test_local_share.joinpath("ULWGL_VERSION.json").open(
            mode="w"
        ) as file:
            file.write(data)
        json_local = ulwgl_util._get_json(self.test_local_share, "ULWGL_VERSION.json")

        self.assertTrue(
            self.test_local_share.joinpath("ULWGL_VERSION.json").is_file(),
            "Expected ULWGL_VERSION.json to be in local share",
        )

        # Update
        result = ulwgl_util._update_ulwgl(
            self.test_user_share,
            self.test_local_share,
            self.test_compat,
            json_root,
            json_local,
        )

        self.assertFalse(result, "Expected None when calling _update_ulwgl")

        # Now, check the state of .local/share/ULWGL
        # We expect the relevant files to be restored

        # Check if the configuration files are equal because we update this on every update of the tools
        with self.test_user_share.joinpath("ULWGL_VERSION.json").open(
            mode="rb"
        ) as file1:
            root = file1.read()
            local = b""
            with self.test_local_share.joinpath("ULWGL_VERSION.json").open(
                mode="rb"
            ) as file2:
                local = file2.read()
            self.assertEqual(
                hashlib.blake2b(root).digest(),
                hashlib.blake2b(local).digest(),
                "Expected configuration files to be the same",
            )

        # Runner
        self.assertTrue(
            self.test_compat.joinpath("ULWGL-Launcher").is_dir(),
            "Expected ULWGL-Launcher in compat",
        )

        for file in self.test_compat.joinpath("ULWGL-Launcher").glob("*"):
            src = b""
            dst = b""

            if file.name == "ulwgl-run":
                self.assertEqual(
                    self.test_user_share.joinpath(
                        "ULWGL-Launcher", "ulwgl-run"
                    ).readlink(),
                    self.test_compat.joinpath("ULWGL-Launcher", "ulwgl-run").readlink(),
                    "Expected both symlinks to point to same dest",
                )
                continue

            with file.open(mode="rb") as filer:
                dst = filer.read()
            with self.test_user_share.joinpath("ULWGL-Launcher", file.name).open(
                mode="rb"
            ) as filer:
                src = filer.read()

            self.assertEqual(
                hashlib.blake2b(src).digest(),
                hashlib.blake2b(dst).digest(),
                "Expected files to be equal",
            )

        # Launcher
        for file in self.test_local_share.glob("*.py"):
            if not file.name.startswith("ulwgl_test"):
                src = b""
                dst = b""

                with file.open(mode="rb") as filer:
                    dst = filer.read()
                with self.test_user_share.joinpath(file.name).open(mode="rb") as filer:
                    src = filer.read()

                if hashlib.blake2b(src).digest() != hashlib.blake2b(dst).digest():
                    err = "Files did not get updated"
                    raise AssertionError(err)

        # Runtime Platform
        self.assertTrue(
            self.test_local_share.joinpath(
                json_local["ulwgl"]["versions"]["runtime_platform"]
            ).is_dir(),
            "Expected runtime to in local share",
        )

        for file in self.test_local_share.joinpath(
            json_local["ulwgl"]["versions"]["runtime_platform"]
        ).glob("*"):
            if file.is_file():
                src = b""
                dst = b""

                with file.open(mode="rb") as filer:
                    dst = filer.read()
                with self.test_user_share.joinpath(
                    json_root["ulwgl"]["versions"]["runtime_platform"], file.name
                ).open(mode="rb") as filer:
                    src = filer.read()

                if hashlib.blake2b(src).digest() != hashlib.blake2b(dst).digest():
                    err = "Files did not get updated"
                    raise AssertionError(err)

        # Pressure Vessel
        self.assertTrue(
            self.test_local_share.joinpath("pressure-vessel").is_dir(),
            "Expected pressure vessel to in local share",
        )

        for file in self.test_local_share.joinpath("pressure-vessel").glob("*"):
            if file.is_file():
                src = b""
                dst = b""

                with file.open(mode="rb") as filer:
                    dst = filer.read()
                with self.test_user_share.joinpath("pressure-vessel", file.name).open(
                    mode="rb"
                ) as filer:
                    src = filer.read()

                if hashlib.blake2b(src).digest() != hashlib.blake2b(dst).digest():
                    err = "Files did not get updated"
                    raise AssertionError(err)

    def test_update_ulwgl(self):
        """Test _update_ulwgl by mocking an update to the runtime tools for existing installations.

        NOTE: This is **very** important as the update process involves replacing directories.
        While the directory we're removing is ours, we do **not** want unintended removals
        """
        result = None
        json_local = None
        json_root = ulwgl_util._get_json(self.test_user_share, "ULWGL_VERSION.json")
        py_files = [
            "ulwgl_consts.py",
            "ulwgl_dl_util.py",
            "ulwgl_log.py",
            "ulwgl_plugins.py",
            "ulwgl_run.py",
            "ulwgl_test.py",
            "ulwgl_util.py",
        ]
        rt_files = [
            "run",
            "run-in-sniper",
            "ULWGL",
        ]
        runner_files = [
            "compatibilitytool.vdf",
            "toolmanifest.vdf",
            "ulwgl-run",
        ]
        # Mock an outdated ULWGL_VERSION.json in ~/.local/share/ULWGL
        # Downgrade these files: launcher, runner, runtime_platform, pressure_vessel
        config = {
            "ulwgl": {
                "versions": {
                    "launcher": "0.1-RC2",
                    "runner": "0.1-RC2",
                    "runtime_platform": "sniper_platform_0.20240125.75304",
                    "reaper": "1.0",
                    "pressure_vessel": "v0.20240211.0",
                }
            }
        }
        data = json.dumps(config, indent=4)

        # In .local/share/ULWGL we expect at least these files to exist:
        # +-- ULWGL (root directory)
        # |   +-- pressure-vessel                               (directory)
        # |   +-- *_platform_0.20240125.75304                   (directory)
        # |   +-- run                                           (normal file)
        # |   +-- run-in-*                                      (normal file)
        # |   +-- ULWGL                                         (normal file)
        # |   +-- ULWGL_VERSION.json                            (normal file)
        # |   +-- ulwgl_*.py                                    (normal file)
        # |   +-- ulwgl-run                                     (link file)
        #
        # To test for potential unintended removals in that dir and that a selective update is performed, additional files will be added to the top-level
        # After an update, those files should still exist and the count should be: count_user_share_files - num_test_files + num_foo_files

        # Add foo files to top-level
        self.test_local_share.joinpath("foo").touch()
        self.test_local_share.joinpath("bar").touch()
        self.test_local_share.joinpath("baz").touch()

        # Do the same for compatibilitytools.d as we do **not** want to unintentionally remove the user's Proton directory
        self.test_compat.joinpath("GE-Proton-foo").mkdir()

        # Config
        self.test_local_share.joinpath("ULWGL_VERSION.json").touch()
        with self.test_local_share.joinpath("ULWGL_VERSION.json").open(
            mode="w"
        ) as file:
            file.write(data)
        json_local = ulwgl_util._get_json(self.test_local_share, "ULWGL_VERSION.json")

        self.assertTrue(
            self.test_local_share.joinpath("ULWGL_VERSION.json").is_file(),
            "Expected ULWGL_VERSION.json to be in local share",
        )

        # Mock the launcher files
        for file in py_files:
            if file == "ulwgl-run":
                self.test_local_share.joinpath("ulwgl-run").symlink_to("ulwgl_run.py")
            else:
                with self.test_local_share.joinpath(file).open(mode="w") as filer:
                    filer.write("foo")

        # Mock the runtime files
        self.test_local_share.joinpath(
            json_local["ulwgl"]["versions"]["runtime_platform"]
        ).mkdir()
        self.test_local_share.joinpath(
            json_local["ulwgl"]["versions"]["runtime_platform"], "bar"
        ).touch()
        for file in rt_files:
            with self.test_local_share.joinpath(file).open(mode="w") as filer:
                filer.write("foo")

        # Mock pressure vessel
        self.test_local_share.joinpath("pressure-vessel").mkdir()
        self.test_local_share.joinpath("pressure-vessel", "bar").touch()

        # Mock ULWGL-Launcher
        self.test_compat.joinpath("ULWGL-Launcher").mkdir()
        for file in runner_files:
            if file == "ulwgl-run":
                self.test_compat.joinpath("ulwgl-run").symlink_to("../../../ulwgl-run")
            else:
                with self.test_compat.joinpath(file).open(mode="w") as filer:
                    filer.write("foo")

        # Update
        result = ulwgl_util._update_ulwgl(
            self.test_user_share,
            self.test_local_share,
            self.test_compat,
            json_root,
            json_local,
        )

        self.assertFalse(result, "Expected None when calling _update_ulwgl")

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

        # Verify the count for .local/share/ULWGL
        num_share = len(
            [
                file
                for file in self.test_user_share.glob("*")
                if not file.name.startswith("ulwgl_test")
            ]
        )
        num_local = len([file for file in self.test_local_share.glob("*")])
        self.assertEqual(
            num_share,
            num_local - 3,
            "Expected /usr/share/ULWGL and .local/share/ULWGL to contain same files",
        )

        # Check if the configuration files are equal because we update this on every update of the tools
        with self.test_user_share.joinpath("ULWGL_VERSION.json").open(
            mode="rb"
        ) as file1:
            root = file1.read()
            local = b""
            with self.test_local_share.joinpath("ULWGL_VERSION.json").open(
                mode="rb"
            ) as file2:
                local = file2.read()
            self.assertEqual(
                hashlib.blake2b(root).digest(),
                hashlib.blake2b(local).digest(),
                "Expected configuration files to be the same",
            )

        # Runner
        # The hashes should be compared because we written data in the mocked files
        self.assertTrue(
            self.test_compat.joinpath("ULWGL-Launcher").is_dir(),
            "Expected ULWGL-Launcher in compat",
        )

        # Verify the count for .local/share/Steam/ULWGL-Launcher
        num_share = len(
            [file for file in self.test_user_share.joinpath("ULWGL-Launcher").glob("*")]
        )
        num_local = len(
            [file for file in self.test_compat.joinpath("ULWGL-Launcher").glob("*")]
        )
        self.assertEqual(
            num_share,
            num_local,
            "Expected .local/share/Steam/compatibilitytools.d/ULWGL-Launcher and /usr/share/ULWGL/ULWGL-Launcher to contain same files",
        )

        for file in self.test_compat.joinpath("ULWGL-Launcher").glob("*"):
            src = b""
            dst = b""

            if file.name == "ulwgl-run":
                self.assertEqual(
                    self.test_user_share.joinpath(
                        "ULWGL-Launcher", "ulwgl-run"
                    ).readlink(),
                    self.test_compat.joinpath("ULWGL-Launcher", "ulwgl-run").readlink(),
                    "Expected both symlinks to point to same dest",
                )
                continue

            with file.open(mode="rb") as filer:
                dst = filer.read()
            with self.test_user_share.joinpath("ULWGL-Launcher", file.name).open(
                mode="rb"
            ) as filer:
                src = filer.read()

            self.assertEqual(
                hashlib.blake2b(src).digest(),
                hashlib.blake2b(dst).digest(),
                "Expected files to be equal",
            )

        # Launcher
        for file in self.test_local_share.glob("*.py"):
            if not file.name.startswith("ulwgl_test"):
                src = b""
                dst = b""

                with file.open(mode="rb") as filer:
                    dst = filer.read()
                with self.test_user_share.joinpath(file.name).open(mode="rb") as filer:
                    src = filer.read()

                if hashlib.blake2b(src).digest() != hashlib.blake2b(dst).digest():
                    err = "Files did not get updated"
                    raise AssertionError(err)

        # Runtime Platform
        self.assertTrue(
            self.test_local_share.joinpath(
                json_local["ulwgl"]["versions"]["runtime_platform"]
            ).is_dir(),
            "Expected runtime to in local share",
        )

        for file in self.test_local_share.joinpath(
            json_local["ulwgl"]["versions"]["runtime_platform"]
        ).glob("*"):
            if file.is_file():
                src = b""
                dst = b""

                with file.open(mode="rb") as filer:
                    dst = filer.read()
                with self.test_user_share.joinpath(
                    json_root["ulwgl"]["versions"]["runtime_platform"], file.name
                ).open(mode="rb") as filer:
                    src = filer.read()

                if hashlib.blake2b(src).digest() != hashlib.blake2b(dst).digest():
                    err = "Files did not get updated"
                    raise AssertionError(err)

        # Pressure Vessel
        self.assertTrue(
            self.test_local_share.joinpath("pressure-vessel").is_dir(),
            "Expected pressure vessel to in local share",
        )

        for file in self.test_local_share.joinpath("pressure-vessel").glob("*"):
            if file.is_file():
                src = b""
                dst = b""

                with file.open(mode="rb") as filer:
                    dst = filer.read()
                with self.test_user_share.joinpath("pressure-vessel", file.name).open(
                    mode="rb"
                ) as filer:
                    src = filer.read()

                if hashlib.blake2b(src).digest() != hashlib.blake2b(dst).digest():
                    err = "Files did not get updated"
                    raise AssertionError(err)

    def test_install_ulwgl(self):
        """Test _install_ulwgl by mocking a first launch.

        At first launch, the directory /usr/share/ULWGL is expected to be populated by distribution's package manager
        This function is expected to be run when ~/.local/share/ULWGL is empty
        The contents of ~/.local/share/ULWGL should be nearly identical to /usr/share/ULWGL, with the exception of the ULWGL-Launcher files
        ULWGL-Launcher is expcted to be copied to compatibilitytools.d
        """
        result = None
        runner_files = {"compatibilitytool.vdf", "toolmanifest.vdf", "ulwgl-run"}
        py_files = {
            "ulwgl_consts.py",
            "ulwgl_dl_util.py",
            "ulwgl_log.py",
            "ulwgl_plugins.py",
            "ulwgl_run.py",
            "ulwgl_test.py",
            "ulwgl_util.py",
        }
        json = ulwgl_util._get_json(self.test_user_share, "ULWGL_VERSION.json")

        # Mock setting up the runtime
        # In the real usage, we callout to acquire the archive and extract to .local/share/ULWGL
        with patch.object(
            ulwgl_util,
            "setup_runtime",
            return_value=None,
        ):
            result = ulwgl_util._install_ulwgl(
                self.test_user_share, self.test_local_share, self.test_compat, json
            )
            ulwgl_util.copyfile_tree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
            )
            ulwgl_util.copyfile_reflink(
                Path(self.test_user_share, "run"), Path(self.test_local_share, "run")
            )
            ulwgl_util.copyfile_reflink(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            ulwgl_util.copyfile_reflink(
                Path(self.test_user_share, "ULWGL"),
                Path(self.test_local_share, "ULWGL"),
            )

        # Verify the state of the local share directory
        self.assertFalse(result, "Expected None after calling _install_ulwgl")

        # Config
        self.assertTrue(
            Path(self.test_user_share, "ULWGL_VERSION.json").is_file(),
            "Expected ULWGL_VERSION.json to exist",
        )

        # ULWGL-Launcher
        self.assertTrue(
            Path(self.test_user_share, "ULWGL-Launcher").is_dir(),
            "Expected ULWGL-Launcher to exist",
        )
        for file in Path(self.test_compat, "ULWGL-Launcher").glob("*"):
            if file.name not in runner_files:
                err = "A non-runner file was copied"
                raise AssertionError(err)
            if file in runner_files and file.is_symlink():
                self.assertEqual(
                    file.readlink(),
                    Path("../../../ulwgl-run"),
                    "Expected ulwgl-run symlink to exist",
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
            Path(self.test_local_share, "ULWGL").is_file(), "Expected ULWGL to exist"
        )

        # Python files
        self.assertTrue(
            list(self.test_local_share.glob("*.py")),
            "Expected Python files to exist",
        )
        for file in self.test_local_share.glob("*.py"):
            if file.name not in py_files:
                err = "A non-launcher file was copied"
                raise AssertionError(err)

        # Symlink
        self.assertTrue(
            Path(self.test_local_share, "ulwgl-run").is_symlink(),
            "Expected ULWGL to exist",
        )
        self.assertEqual(
            Path(self.test_local_share, "ulwgl-run").readlink(),
            Path("ulwgl_run.py"),
            "Expected ulwgl-run -> ulwgl_run.py",
        )

    def test_copy_tree(self):
        """Test copyfile_tree.

        An error should not be raised in the process of a simple copy transaction nor during recursion -- infinite recursion or callstack limit.
        """
        result = False
        test_dir = Path("tmp.RkjsKEm8pZ")

        test_dir.mkdir(exist_ok=True)
        test_dir.joinpath("ULWGL_VERSION.json").touch()
        with test_dir.joinpath("ULWGL_VERSION.json").open(mode="w") as file:
            file.write(self.test_config)

        self.assertTrue(
            test_dir.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to exist in test /usr/share/ULWGL",
        )
        self.assertFalse(
            self.test_local_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to not exist in test .local/share/ULWGL",
        )

        # Copy the test dir contents into the other test dir
        result = ulwgl_util.copyfile_tree(test_dir, self.test_local_share)

        # Confirm the state of the dest dir
        self.assertTrue(result, "Expected False after calling copyfile_tree")
        self.assertTrue(
            any(self.test_local_share.iterdir()),
            "Expected destination dir to not be empty",
        )
        self.assertEqual(
            len(list(self.test_local_share.glob("*"))), 1, "Expected only one file"
        )
        self.assertTrue(
            self.test_local_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to be copied",
        )

        if test_dir.exists():
            test_dir.joinpath("ULWGL_VERSION.json").unlink()
            test_dir.rmdir()

    def test_copy_err(self):
        """Test copyfile_reflink for error.

        An OSError is expected to be raised if the error number is not: EXDEV, ENOSYS, EINVAL
        """
        self.assertTrue(
            self.test_user_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to exist in test /usr/share/ULWGL",
        )

        with patch("os.copy_file_range") as mock_function:
            # Mock the OS error that is not EXDEV ENOSYS EINVAL
            # We want to fallback to normal copy
            mock_function.side_effect = OSError(errno.EPERM, "")

            with self.assertRaisesRegex(OSError, "Errno 1"):
                ulwgl_util.copyfile_reflink(
                    self.test_user_share.joinpath("ULWGL_VERSION.json"),
                    self.test_local_share.joinpath("ULWGL_VERSION.json"),
                )

    def test_copy_fallback(self):
        """Test copyfile_reflink in the case of error.

        For systems that do not support copy_file_range, we fallback to normal copy
        """
        result = None
        src = b""
        dst = b""

        self.assertTrue(
            self.test_user_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to exist in test /usr/share/ULWGL",
        )
        self.assertFalse(
            self.test_local_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to not exist in test .local/share/ULWGL",
        )

        with patch("os.copy_file_range") as mock_function:
            # Mock the OS error
            # We want to fallback to normal copy
            mock_function.side_effect = OSError(errno.ENOSYS, "")

            # Copy ULWGL_VERSION.json to the mocked .local/share/ULWGL
            result = ulwgl_util.copyfile_reflink(
                self.test_user_share.joinpath("ULWGL_VERSION.json"),
                self.test_local_share.joinpath("ULWGL_VERSION.json"),
            )

        self.assertFalse(result, "Expected None when calling copyfile_reflink")
        self.assertTrue(
            self.test_local_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to be copied to local share",
        )

        # Verify the integrity of data and metadata
        with self.test_user_share.joinpath("ULWGL_VERSION.json").open(
            mode="rb"
        ) as file:
            src = file.read()

        with self.test_local_share.joinpath("ULWGL_VERSION.json").open(
            mode="rb"
        ) as file:
            dst = file.read()

        self.assertEqual(
            hashlib.blake2b(src).digest(),
            hashlib.blake2b(dst).digest(),
            "Expected the same files",
        )
        self.assertEqual(
            self.test_user_share.joinpath("ULWGL_VERSION.json").stat().st_mode,
            self.test_local_share.joinpath("ULWGL_VERSION.json").stat().st_mode,
            "Expected metadata to be equal",
        )

    def test_copy(self):
        """Test copyfile_reflink.

        If the filesystem supports reflink, we try to create a shallow copy of files. Otherwise, we fallback to normal copy
        An error should not be raised in the process of copying a source file to a destination
        The test assumes that there is only one filesystem on the host.
        However, in the real usage, it's possible for the root partition filesystem to be different than the home partition (e.g. Steam Deck)

        NOTE: We do not test if the file is a shallow copy as it's not easily verifiable through Python and depends on the user's system
        Therefore, when running the test locally, most likely only one branch is effectively tested
        """
        result = None
        src = b""
        dst = b""

        self.assertTrue(
            self.test_user_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to exist in test /usr/share/ULWGL",
        )
        self.assertFalse(
            self.test_local_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to not exist in test .local/share/ULWGL",
        )

        # Copy ULWGL_VERSION.json to the mocked .local/share/ULWGL
        result = ulwgl_util.copyfile_reflink(
            self.test_user_share.joinpath("ULWGL_VERSION.json"),
            self.test_local_share.joinpath("ULWGL_VERSION.json"),
        )

        self.assertFalse(result, "Expected None when calling copyfile_reflink")
        self.assertTrue(
            self.test_local_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to be copied to local share",
        )

        # Verify the integrity
        with self.test_user_share.joinpath("ULWGL_VERSION.json").open(
            mode="rb"
        ) as file:
            src = file.read()

        with self.test_local_share.joinpath("ULWGL_VERSION.json").open(
            mode="rb"
        ) as file:
            dst = file.read()

        self.assertEqual(
            hashlib.blake2b(src).digest(),
            hashlib.blake2b(dst).digest(),
            "Expected the same files",
        )
        self.assertEqual(
            self.test_user_share.joinpath("ULWGL_VERSION.json").stat().st_mode,
            self.test_local_share.joinpath("ULWGL_VERSION.json").stat().st_mode,
            "Expected metadata to be equal",
        )

    def test_get_json_err(self):
        """Test _get_json when specifying a corrupted ULWGL_VERSION.json file.

        A ValueError should be raised because we expect 'ulwgl' and 'version' keys to exist
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
            "ulwgl": {
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
        Path(self.test_user_share, "ULWGL_VERSION.json").unlink(missing_ok=True)

        Path(self.test_user_share, "ULWGL_VERSION.json").touch()
        with Path(self.test_user_share, "ULWGL_VERSION.json").open(mode="w") as file:
            file.write(test_config)

        # Test when "ulwgl" doesn't exist
        with self.assertRaisesRegex(ValueError, "load"):
            ulwgl_util._get_json(self.test_user_share, "ULWGL_VERSION.json")

        # Test when "versions" doesn't exist
        Path(self.test_user_share, "ULWGL_VERSION.json").unlink(missing_ok=True)

        Path(self.test_user_share, "ULWGL_VERSION.json").touch()
        with Path(self.test_user_share, "ULWGL_VERSION.json").open(mode="w") as file:
            file.write(test_config2)

        with self.assertRaisesRegex(ValueError, "load"):
            ulwgl_util._get_json(self.test_user_share, "ULWGL_VERSION.json")

    def test_get_json_foo(self):
        """Test _get_json when not specifying ULWGL_VERSION.json as the second argument.

        A FileNotFoundError should be raised
        """
        with self.assertRaisesRegex(FileNotFoundError, "configuration"):
            ulwgl_util._get_json(self.test_user_share, "foo")

    def test_get_json(self):
        """Test _get_json.

        This function is used to verify the existence and integrity of ULWGL_VERSION.json file during the setup process
        ULWGL_VERSION.json is used to synchronize the state of two directories, namely: /usr/share/ULWGL and ~/.local/share/ULWGL

        An error should not be raised when passed a JSON we expect
        """
        result = None

        self.assertTrue(
            self.test_user_share.joinpath("ULWGL_VERSION.json").exists(),
            "Expected ULWGL_VERSION.json to exist",
        )

        result = ulwgl_util._get_json(self.test_user_share, "ULWGL_VERSION.json")
        self.assertIsInstance(result, dict, "Expected a dict")

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

    def test_setup_pfx_symlinks_else(self):
        """Test setup_pfx in the case both steamuser and unixuser exist in some form.

        Tests the case when they are symlinks
        An error should not be raised and we should just do nothing
        """
        result = None
        pattern = r"^/home/[\w\d]+"
        user = ulwgl_util.UnixUser()
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
            user.get_user()
        ).expanduser().symlink_to(Path(self.test_file).absolute())
        Path(unexpanded_path).joinpath("drive_c/users").joinpath(
            "steamuser"
        ).expanduser().symlink_to(Path(self.test_file).absolute())

        result = ulwgl_run.setup_pfx(unexpanded_path)

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
        user = ulwgl_util.UnixUser()
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(
                Path(self.test_file).cwd().as_posix() + "/" + self.test_file
            ).as_posix(),
        )

        # Create only the user dir
        Path(unexpanded_path).joinpath("drive_c/users").joinpath(
            user.get_user()
        ).expanduser().mkdir(parents=True, exist_ok=True)

        result = ulwgl_run.setup_pfx(unexpanded_path)

        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and tracked_files file",
        )

        # Verify steamuser -> unix user
        self.assertTrue(
            Path(self.test_file).joinpath("drive_c/users/steamuser").is_symlink(),
            "Expected steamuser to be a symbolic link",
        )
        self.assertEqual(
            Path(self.test_file).joinpath("drive_c/users/steamuser").readlink(),
            Path(user.get_user()),
            "Expected steamuser -> user",
        )

    def test_setup_pfx_symlinks_steamuser(self):
        """Test setup_pfx for symbolic link to wine.

        Tests the case when only steamuser exist and the user dir does not exist
        """
        result = None
        user = ulwgl_util.UnixUser()
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

        result = ulwgl_run.setup_pfx(unexpanded_path)

        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and tracked_files file",
        )

        # Verify unixuser -> steamuser
        self.assertTrue(
            Path(self.test_file + "/drive_c/users/steamuser").is_dir(),
            "Expected steamuser to be created",
        )
        self.assertTrue(
            Path(unexpanded_path + "/drive_c/users/" + user.get_user())
            .expanduser()
            .is_symlink(),
            "Expected symbolic link for unixuser",
        )
        self.assertEqual(
            Path(self.test_file)
            .joinpath(f"drive_c/users/{user.get_user()}")
            .readlink(),
            Path("steamuser"),
            "Expected unixuser -> steamuser",
        )

    def test_setup_pfx_symlinks(self):
        """Test setup_pfx for valid symlinks.

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
        user = ulwgl_util.UnixUser()
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
        # For new prefixes, steamuser should exist and a user symlink
        self.assertTrue(
            Path(self.test_file + "/drive_c/users/steamuser").is_dir(),
            "Expected steamuser to be created",
        )
        self.assertTrue(
            Path(self.test_file + "/drive_c/users/" + user.get_user())
            .expanduser()
            .is_symlink(),
            "Expected symlink of username -> steamuser",
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
