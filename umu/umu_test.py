import argparse
import hashlib
import os
import re
import sys
import tarfile
import unittest
from argparse import Namespace
from array import array
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from importlib.util import find_spec
from pathlib import Path
from pwd import getpwuid
from shutil import copy, copytree, move, rmtree
from subprocess import CompletedProcess
from tempfile import NamedTemporaryFile, TemporaryDirectory, TemporaryFile, gettempdir
from unittest.mock import MagicMock, Mock, patch

from Xlib.display import Display
from Xlib.error import DisplayConnectionError
from Xlib.protocol.rq import Event
from Xlib.X import CreateNotify
from Xlib.xobject.drawable import Window

sys.path.append(str(Path(__file__).parent.parent))

from umu import __main__, umu_proton, umu_run, umu_runtime, umu_util, vdf


class TestGameLauncher(unittest.TestCase):
    """Test suite for umu-launcher."""

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
            "WINE": "",
            "WINELOADER": "",
            "WINESERVER": "",
            "WINETRICKS_LATEST_VERSION_CHECK": "",
            "LD_PRELOAD": "",
            "WINETRICKS_SUPER_QUIET": "",
            "UMU_NO_RUNTIME": "",
            "UMU_RUNTIME_UPDATE": "",
            "STEAM_COMPAT_TRANSCODED_MEDIA_PATH": "",
            "STEAM_COMPAT_MEDIA_PATH": "",
            "STEAM_FOSSILIZE_DUMP_PATH": "",
            "DXVK_STATE_CACHE_PATH": "",
            "UMU_NO_PROTON": "",
            "RUNTIMEPATH": "",
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
        self.test_cache_home = Path("./tmp.Ye0g13HmTy")
        # Cache
        self.test_cache = Path("./tmp.5HYdpddgvs")
        # Steam compat dir
        self.test_compat = Path("./tmp.ZssGZoiNod")
        # umu compat dir
        self.test_umu_compat = Path("./tmp.tu692WxQHH")
        # umu-proton dir
        self.test_proton_dir = Path("./UMU-Proton-5HYdpddgvs")
        # umu-proton release
        self.test_archive = Path(self.test_cache).joinpath(
            f"{self.test_proton_dir}.tar.gz"
        )
        # /usr/share/umu
        self.test_user_share = Path("./tmp.BXk2NnvW2m")
        # ~/.local/share/Steam/compatibilitytools.d
        self.test_runtime_versions = (
            ("sniper", "steamrt3", "1628350"),
            ("soldier", "steamrt2", "1391110"),
        )
        self.test_runtime_default = self.test_runtime_versions[0]
        self.test_local_share_parent = Path("./tmp.aDl73CbQCP")
        self.test_local_share = self.test_local_share_parent.joinpath(
            self.test_runtime_default[1]
        )
        # Wine prefix
        self.test_winepfx = Path("./tmp.AlfLPDhDvA")
        # Thread pool and connection pool instances
        self.test_session_pools = (MagicMock(), MagicMock())

        # /usr
        self.test_usr = Path("./tmp.QnZRGFfnqH")

        self.test_winepfx.mkdir(exist_ok=True)
        self.test_user_share.mkdir(exist_ok=True)
        self.test_local_share.mkdir(parents=True, exist_ok=True)
        self.test_cache.mkdir(exist_ok=True)
        self.test_compat.mkdir(exist_ok=True)
        self.test_proton_dir.mkdir(exist_ok=True)
        self.test_usr.mkdir(exist_ok=True)
        self.test_cache_home.mkdir(exist_ok=True)
        self.test_umu_compat.mkdir(exist_ok=True)

        # Mock the launcher files
        Path(self.test_user_share, "umu_consts.py").touch()
        Path(self.test_user_share, "umu_proton.py").touch()
        Path(self.test_user_share, "umu_log.py").touch()
        Path(self.test_user_share, "umu_plugins.py").touch()
        Path(self.test_user_share, "umu_run.py").touch()
        Path(self.test_user_share, "umu_runtime.py").touch()
        Path(self.test_user_share, "umu-run").symlink_to("umu_run.py")
        Path(self.test_user_share, "umu_util.py").touch()

        # Mock the runtime files
        Path(self.test_user_share, "sniper_platform_0.20240125.75305").mkdir()
        Path(self.test_user_share, "sniper_platform_0.20240125.75305", "foo").touch()
        Path(self.test_user_share, "run").touch()
        Path(self.test_user_share, "run-in-sniper").touch()
        Path(self.test_user_share, "umu").touch()
        mock_steamrt_toolmanifest = {
            "manifest": {
                "commandline": "/_v2-entry-point --verb=%verb% --",
                "filter_exclusive_priority": "3",
                "version": "2",
                "use_tool_subprocess_reaper": "1",
                "compatmanager_layer_name": "container-runtime",
            }
        }
        Path(self.test_user_share, "toolmanifest.vdf").write_text(
            vdf.dumps(mock_steamrt_toolmanifest)
        )

        # Mock pressure vessel
        Path(self.test_user_share, "pressure-vessel", "bin").mkdir(parents=True)
        Path(self.test_user_share, "pressure-vessel", "foo").touch()
        Path(self.test_user_share, "pressure-vessel", "bin", "pv-verify").touch()
        Path(
            self.test_user_share,
            "pressure-vessel",
            "bin",
            "steam-runtime-launch-client",
        ).write_text('#!/bin/sh\nexec "$@"\n')
        Path(
            self.test_user_share,
            "pressure-vessel",
            "bin",
            "steam-runtime-launch-client",
        ).chmod(0o700)

        # Mock the proton file in the dir
        self.test_proton_dir.joinpath("proton").touch(exist_ok=True)
        mock_proton_compatibilitytool = {
            "compatibilitytools": {
                "compat_tools": {
                    self.test_proton_dir.name: {
                        "install_path": ".",
                        "display_name": self.test_proton_dir.name,
                        "from_oslist": "windows",
                        "to_oslist": "linux",
                    }
                }
            }
        }
        self.test_proton_dir.joinpath("compatibilitytool.vdf").write_text(
            vdf.dumps(mock_proton_compatibilitytool)
        )
        mock_proton_toolmanifest = {
            "manifest": {
                "version": "2",
                "commandline": "/proton %verb%",
                "require_tool_appid": "1628350",
                "use_sessions": "1",
                "compatmanager_layer_name": "proton",
            }
        }
        self.test_proton_dir.joinpath("toolmanifest.vdf").write_text(
            vdf.dumps(mock_proton_toolmanifest)
        )

        # Mock the release downloaded in the cache:
        # tmp.5HYdpddgvs/umu-Proton-5HYdpddgvs.tar.gz
        # Expected directory structure within the archive:
        #
        # +-- umu-Proton-5HYdpddgvs (root directory)
        # |   +-- proton              (normal file)
        with tarfile.open(self.test_archive.as_posix(), "w:gz") as tar:
            tar.add(
                self.test_proton_dir.as_posix(),
                arcname=self.test_proton_dir.as_posix(),
            )

        Path(self.test_file).mkdir(exist_ok=True)
        Path(self.test_exe).touch()

    def tearDown(self):
        """Unset environment variables and delete test files after tests."""
        for key in self.env:
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

        if self.test_local_share_parent.exists():
            rmtree(self.test_local_share_parent)

        if self.test_winepfx.exists():
            rmtree(self.test_winepfx.as_posix())

        if self.test_usr.exists():
            rmtree(self.test_usr.as_posix())

        if self.test_cache_home.exists():
            rmtree(self.test_cache_home.as_posix())

        if self.test_umu_compat.exists():
            rmtree(self.test_umu_compat.as_posix())

    def test_get_umu_version_from_manifest_unknownappid(self):
        """Test get_umu_version_from_manifest.

        Expects None when a container runtime not already known cannot be found
        in the compatibility tool's manifest.
        """
        result = None
        # A text file implementing the compatibility tool interface is expected
        # See https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/v0.20251103.0/docs/steam-compat-tool-interface.md?ref_type=tags
        mock_manifest = {
            "manifest": {
                "version": "2",
                "commnadline": "/proton %verb%",
                "require_tool_appid": "769",
                "use_sessions": "1",
                "compatmanager_layer_name": "proton",
            }
        }

        with TemporaryDirectory() as mock_proton:
            Path(mock_proton, "toolmanifest.vdf").write_text(
                vdf.dumps(mock_manifest), encoding="utf-8"
            )
            with self.assertRaises(KeyError):
                result = umu_runtime.CompatLayer(
                    Path(mock_proton), Path()
                ).required_runtime
                self.assertIsNone(result, f"Expected None, received '{result}'")

    def test_get_umu_version_from_manifest_noappid(self):
        """Test get_umu_version_from_manifest.

        Expects None when a known container runtime cannot be found in the
        compatibility tool's manifest because the expected value does not
        exist.
        """
        mock_container_runtimes = (
            ("host", "", ""),
            ("sniper", "steamrt3", "1628350"),
            ("soldier", "steamrt2", "1391110"),
        )
        mock_manifest = (
            '"manifest"\n'
            "{\n"
            '  "version" "2"\n'
            '  "commandline" "/proton %verb%"\n'
            '  "use_sessions" "1"\n'
            '  "compatmanager_layer_name" "proton"\n'
            "}"
        )

        with TemporaryDirectory() as mock_proton:
            Path(mock_proton, "toolmanifest.vdf").write_text(
                mock_manifest, encoding="utf-8"
            )
            result = umu_runtime.CompatLayer(Path(mock_proton), Path()).required_runtime
            self.assertEqual(
                result.as_tuple(),
                mock_container_runtimes[0],
                f"Expected None, received '{result}'",
            )

    def test_get_umu_version_from_manifest(self):
        """Test get_umu_version_from_manifest.

        Expects a tuple representing a known container runtime.
        """
        result = None
        mock_container_runtimes = (
            ("sniper", "steamrt3", "1628350"),
            ("soldier", "steamrt2", "1391110"),
        )
        mock_manifest = (
            '"manifest"\n'
            "{\n"
            '  "version" "2"\n'
            '  "commandline" "/proton %verb%"\n'
            '  "require_tool_appid" "1628350"\n'
            '  "use_sessions" "1"\n'
            '  "compatmanager_layer_name" "proton"\n'
            "}"
        )

        with TemporaryDirectory() as mock_proton:
            Path(mock_proton, "toolmanifest.vdf").write_text(
                mock_manifest, encoding="utf-8"
            )
            result = umu_runtime.CompatLayer(Path(mock_proton), Path()).required_runtime
            self.assertEqual(
                result.as_tuple(),
                mock_container_runtimes[0],
                f"Expected '{mock_container_runtimes[0]}, received {result}'",
            )

    def test_resolve_umu_version_none(self):
        """Test resolve_umu_version.

        Expects None when a known, required runtime is not found in the
        compatibility tool's manifest.
        """
        mock_manifest = (
            '"manifest"\n'
            "{\n"
            '  "version" "2"\n'
            '  "commandline" "/proton %verb%"\n'
            '  "require_tool_appid" "769"\n'
            '  "use_sessions" "1"\n'
            '  "compatmanager_layer_name" "proton"\n'
            "}"
        )

        with TemporaryDirectory() as mock_proton:
            Path(mock_proton, "toolmanifest.vdf").write_text(
                mock_manifest, encoding="utf-8"
            )
            self.assertTrue(
                "RUNTIMEPATH" not in os.environ,
                f"Expected None, received '{os.environ.get('RUNTIMEPATH')}",
            )
            self.assertTrue(
                "UMU_NO_PROTON" not in os.environ,
                f"Expected None, received '{os.environ.get('UMU_NO_PROTON')}",
            )
            os.environ["PROTONPATH"] = mock_proton
            with self.assertRaises(KeyError):
                result = umu_run.resolve_runtime()
                self.assertIsNone(result, f"Expected None, received '{result}'")

    def test_resolve_umu_version_noproton(self):
        """Test resolve_umu_version when UMU_NO_PROTON is set.

        Expects a tuple representing the known latest container runtime.
        In this case, a parsing of a manifest will not a occur.
        """
        result = None
        mock_container_runtimes = (
            ("sniper", "steamrt3", "1628350"),
            ("soldier", "steamrt2", "1391110"),
        )
        mock_expected = tuple(list(mock_container_runtimes[0]))  # noqa

        self.assertTrue(
            "RUNTIMEPATH" not in os.environ,
            f"Expected None, received '{os.environ.get('RUNTIMEPATH')}",
        )
        self.assertTrue(
            "PROTONPATH" not in os.environ,
            f"Expected None, received '{os.environ.get('PROTONPATH')}",
        )
        os.environ["UMU_NO_PROTON"] = "1"
        result = umu_run.resolve_runtime()
        self.assertEqual(
            result,
            mock_expected,
            f"Expected '{mock_expected}', received '{result}'",
        )
        self.assertEqual(
            result,
            mock_container_runtimes[0],
            f"Expected the original instance '{result}'",
        )

    def test_resolve_umu_version_token(self):
        """Test resolve_umu_version when PROTONPATH is a known, valid token.

        Expects a tuple representing the known latest container runtime.
        Known, valid tokens include: GE-Proton. In this case, parsing of a
        manifest will not occur and it is assumed the compatibility tool
        associated with the token uses the latest runtime.
        """
        result = None
        mock_container_runtimes = (
            ("sniper", "steamrt3", "1628350"),
            ("soldier", "steamrt2", "1391110"),
        )
        mock_expected = tuple(list(mock_container_runtimes[0]))  # noqa

        self.assertTrue(
            "RUNTIMEPATH" not in os.environ,
            f"Expected None, received '{os.environ.get('RUNTIMEPATH')}",
        )
        self.assertTrue(
            "UMU_NO_PROTON" not in os.environ,
            f"Expected None, received '{os.environ.get('UMU_NO_PROTON')}",
        )
        os.environ["PROTONPATH"] = "GE-Proton"
        result = umu_run.resolve_runtime()
        self.assertEqual(
            result,
            mock_expected,
            f"Expected '{mock_expected}', received '{result}'",
        )
        self.assertEqual(
            result,
            mock_container_runtimes[0],
            f"Expected the original instance '{result}'",
        )

    def test_resolve_umu_version(self):
        """Test resolve_umu_version when all expected inputs are unset.

        Expects a tuple representing a known container runtime that is the
        latest version. In this case, parsing of a manifest will not occur and
        the launcher will default to the latest known runtime.
        """
        result = None
        mock_container_runtimes = (
            ("sniper", "steamrt3", "1628350"),
            ("soldier", "steamrt2", "1391110"),
        )
        mock_expected = tuple(list(mock_container_runtimes[1]))  # noqa

        self.assertTrue(
            "PROTONPATH" not in os.environ,
            f"Expected None, received '{os.environ.get('PROTONPATH')}",
        )
        self.assertTrue(
            "RUNTIMEPATH" not in os.environ,
            f"Expected None, received '{os.environ.get('RUNTIMEPATH')}",
        )
        self.assertTrue(
            "UMU_NO_PROTON" not in os.environ,
            f"Expected None, received '{os.environ.get('UMU_NO_PROTON')}",
        )
        result = umu_run.resolve_runtime()
        self.assertEqual(
            result,
            mock_container_runtimes[0],
            f"Expected '{mock_expected}', received None",
        )
        self.assertEqual(
            result,
            mock_container_runtimes[0],
            f"Expected the original instance '{result}'",
        )

    def test_resolve_umu_version_runtimepath(self):
        """Test resolve_umu_version when RUNTIMEPATH is set.

        Expects a tuple representing a known container runtime that contains
        the RUNTIMEPATH value. In this case, parsing of a manifest will not
        occur.
        """
        result = None
        mock_container_runtimes = (
            ("sniper", "steamrt3", "1628350"),
            ("soldier", "steamrt2", "1391110"),
        )
        mock_expected = tuple(list(mock_container_runtimes[1]))  # noqa

        self.assertTrue(
            "PROTONPATH" not in os.environ,
            f"Expected None, received '{os.environ.get('PROTONPATH')}",
        )
        self.assertTrue(
            "UMU_NO_PROTON" not in os.environ,
            f"Expected None, received '{os.environ.get('UMU_NO_PROTON')}",
        )
        os.environ["RUNTIMEPATH"] = "steamrt2"
        result = umu_run.resolve_runtime()
        self.assertEqual(
            result,
            mock_expected,
            f"Expected '{mock_expected}', received None",
        )
        self.assertEqual(
            result,
            mock_container_runtimes[1],
            f"Expected the original instance '{result}'",
        )
        self.assertEqual(
            os.environ["RUNTIMEPATH"],
            mock_container_runtimes[1][1],
            f"Expected '{os.environ['RUNTIMEPATH']}' in '{result}'",
        )

    def test_resolve_umu_version_protonpath(self):
        """Test resolve_umu_version when PROTONPATH is set.

        Expects a tuple representing a known container runtime when the
        compatibility tool's required runtime is found in its manifest.
        In this case, the compatibility tool will be searched and parsing
        of a manifest will occur.
        """
        result = None
        mock_manifest = (
            '"manifest"\n'
            "{\n"
            '  "version" "2"\n'
            '  "commandline" "/proton %verb%"\n'
            '  "require_tool_appid" "1628350"\n'
            '  "use_sessions" "1"\n'
            '  "compatmanager_layer_name" "proton"\n'
            "}"
        )
        # The first element represents the latest, known container runtime
        mock_container_runtimes = (
            ("sniper", "steamrt3", "1628350"),
            ("soldier", "steamrt2", "1391110"),
        )
        # Copy the first element because we want to assert immutability
        mock_expected = tuple(list(mock_container_runtimes[0]))  # noqa

        with TemporaryDirectory() as mock_proton:
            Path(mock_proton, "toolmanifest.vdf").write_text(
                mock_manifest, encoding="utf-8"
            )
            self.assertTrue(
                "RUNTIMEPATH" not in os.environ,
                f"Expected None, received '{os.environ.get('RUNTIMEPATH')}",
            )
            self.assertTrue(
                "UMU_NO_PROTON" not in os.environ,
                f"Expected None, received '{os.environ.get('UMU_NO_PROTON')}",
            )
            os.environ["PROTONPATH"] = mock_proton
            result = umu_runtime.CompatLayer(
                Path(os.environ["PROTONPATH"]), Path()
            ).required_runtime
            self.assertEqual(
                result.as_tuple(),
                mock_expected,
                f"Expected '{mock_expected}', received None",
            )
            # Ensure the called function did not mutate the input
            self.assertEqual(
                result.as_tuple(),
                mock_container_runtimes[0],
                f"Expected the original instance '{result}'",
            )

    def test_split_dirfd(self):
        """Test _split_dirfd."""
        with TemporaryDirectory() as file:
            result = None
            mock_path = Path(file, "foo")

            with umu_util._split_dirfd(mock_path) as mock_split:
                result = mock_split
                self.assertIsInstance(
                    result, tuple, f"Expected '{result}' to be a tuple"
                )
                self.assertTrue(
                    os.fstat(result[0]),
                    f"Expected '{result[0]}' to be a file descriptor",
                )
                self.assertEqual(
                    mock_path.name,
                    result[1],
                    f"Expected '{result[1]}' to be '{mock_path.name}'",
                )

    def test_sys_renameat2(self):
        """Test _renameat2 for files when SRC exists and DEST does not exists."""
        with TemporaryDirectory() as file:
            result = None
            mock_src = Path(file, "foo")
            mock_dest = Path(file, "bar")

            mock_src.touch()

            self.assertTrue(
                Path(file, "foo").exists(), f"Expected {Path(file, 'foo')} to exist."
            )
            self.assertFalse(
                Path(file, "bar").exists(),
                f"Expected {Path(file, 'bar')} to not exist.",
            )

            mock_src_fd = None
            mock_dest_fd = None
            try:
                mock_src_fd = os.open(
                    mock_src.parent, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC
                )
                mock_dest_fd = os.open(
                    mock_src.parent, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC
                )
                result = umu_util._renameat2(
                    mock_src_fd,
                    mock_src.name,
                    mock_dest_fd,
                    mock_dest.name,
                    umu_util.Renameat2.RENAME_NOREPLACE,
                )
            finally:
                if mock_src_fd is not None:
                    os.close(mock_src_fd)
                if mock_dest_fd is not None:
                    os.close(mock_dest_fd)

            self.assertIsNone(result, f"Expected '{result}' to be None")
            self.assertTrue(
                Path(file, "bar").exists(), f"Expected {Path(file, 'bar')} to exist."
            )
            self.assertFalse(
                Path(file, "foo").exists(),
                f"Expected {Path(file, 'foo')} to not exist.",
            )

    def test_sys_renameat2_exch(self):
        """Test _renameat2 when SRC and DEST are different directories."""
        with TemporaryDirectory() as file1, TemporaryDirectory() as file2:
            result = None
            mock_src = Path(file1, "foo")
            mock_dest = Path(file2, "bar")

            mock_src.touch()
            mock_dest.touch()

            self.assertTrue(
                Path(file1, "foo").exists(), f"Expected {Path(file1, 'foo')} to exist."
            )
            self.assertTrue(
                Path(file2, "bar").exists(), f"Expected {Path(file2, 'bar')} to exist."
            )

            mock_src_fd = None
            mock_dest_fd = None
            try:
                mock_src_fd = os.open(
                    mock_src.parent, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC
                )
                mock_dest_fd = os.open(
                    mock_dest.parent, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC
                )
                result = umu_util._renameat2(
                    mock_src_fd,
                    str(mock_src.parent),
                    mock_dest_fd,
                    str(mock_dest.parent),
                    umu_util.Renameat2.RENAME_EXCHANGE,
                )
            finally:
                if mock_src_fd is not None:
                    os.close(mock_src_fd)
                if mock_dest_fd is not None:
                    os.close(mock_dest_fd)

            self.assertIsNone(result, f"Expected '{result}' to be None")
            self.assertTrue(
                Path(file1, "bar").exists(), f"Expected {Path(file1, 'bar')} to exist."
            )
            self.assertFalse(
                Path(file1, "foo").exists(),
                f"Expected {Path(file1, 'foo')} to not exist.",
            )
            self.assertTrue(
                Path(file2, "foo").exists(), f"Expected {Path(file2, 'foo')} to exist."
            )
            self.assertFalse(
                Path(file2, "bar").exists(),
                f"Expected {Path(file1, 'bar')} to not exist.",
            )

    def test_exchange(self):
        """Test exchange."""
        with TemporaryDirectory() as file1, TemporaryDirectory() as file2:
            result = None

            Path(file1, "foo").touch()
            Path(file2, "bar").touch()

            self.assertTrue(
                Path(file1, "foo").exists(), f"Expected {Path(file1, 'foo')} to exist."
            )
            self.assertTrue(
                Path(file2, "bar").exists(), f"Expected {Path(file2, 'bar')} to exist."
            )

            result = umu_util.exchange(Path(file1), Path(file2))

            self.assertIsNone(result, f"Expected '{result}' to be None")
            self.assertTrue(
                Path(file1, "bar").exists(), f"Expected {Path(file1, 'bar')} to exist."
            )
            self.assertFalse(
                Path(file1, "foo").exists(),
                f"Expected {Path(file1, 'foo')} to not exist.",
            )
            self.assertTrue(
                Path(file2, "foo").exists(), f"Expected {Path(file2, 'foo')} to exist."
            )
            self.assertFalse(
                Path(file2, "bar").exists(),
                f"Expected {Path(file1, 'bar')} to not exist.",
            )

    def test_renameat2(self):
        """Test renameat2."""
        with TemporaryDirectory() as file1, TemporaryDirectory() as file2:
            result = None

            Path(file1, "foo").touch()
            Path(file2, "bar").touch()

            self.assertTrue(
                Path(file1, "foo").exists(), f"Expected {Path(file1, 'foo')} to exist."
            )
            self.assertTrue(
                Path(file2, "bar").exists(), f"Expected {Path(file2, 'bar')} to exist."
            )

            result = umu_util.renameat2(
                Path(file1), Path(file2), umu_util.Renameat2.RENAME_EXCHANGE
            )

            self.assertIsNone(result, f"Expected '{result}' to be None")
            self.assertTrue(
                Path(file1, "bar").exists(), f"Expected {Path(file1, 'bar')} to exist."
            )
            self.assertFalse(
                Path(file1, "foo").exists(),
                f"Expected {Path(file1, 'foo')} to not exist.",
            )
            self.assertTrue(
                Path(file2, "foo").exists(), f"Expected {Path(file2, 'foo')} to exist."
            )
            self.assertFalse(
                Path(file2, "bar").exists(),
                f"Expected {Path(file1, 'bar')} to not exist.",
            )

    def test_get_lines_split(self):
        """Test _get_lines_split.

        Expects a Generator to yield values of type str.
        """
        result = None
        mock_proc_filesystems = (
            "nodev	sysfs\n"
            "nodev	tmpfs\n"
            "nodev	bdev\n"
            "nodev	proc\n"
            "nodev	cgroup\n"
            "nodev	cgroup2\n"
            "       ext3"
        )

        with NamedTemporaryFile(mode="w", encoding="utf-8") as tmp:
            tmp.write(mock_proc_filesystems)
            tmp.seek(0)
            result = umu_util._get_lines_split(Path(tmp.name), None, 2)
            self.assertTrue(
                isinstance(result, Generator), f"Expected '{result}' to be a Generator"
            )
            lines = iter(
                line.split(None, 2) for line in mock_proc_filesystems.split("\n")
            )
            expected = [line for line in lines if line]
            result = list(result)
            self.assertEqual(
                expected, result, f"Expected '{expected}' to be '{result}'"
            )
            self.assertTrue(
                any(val for val in result if not isinstance(val, str)),
                f"Expected items in '{result}' to be str",
            )
            self.assertTrue(
                any(val for val in expected if not isinstance(val, str)),
                f"Expected items in '{expected}' to be str",
            )

    def test_get_supported_fs(self):
        """Test _get_supported_fs.

        Expects a set to be returned.
        """
        result = None

        # Skip this test if /proc does not exist
        if not Path("/proc").exists():
            err = "/proc does not exists"
            self.skipTest(err)

        result = umu_util._get_supported_fs()
        self.assertTrue(isinstance(result, set), f"Expected '{result}' to be a set")

    def test_fsck_path(self):
        """Test _fsck_path.

        Expects a boolean to be returned.
        """
        result = None
        filesystem = "tmpfs"

        # Skip this test if /proc does not exist
        if not Path("/proc").exists():
            err = "/proc does not exists"
            self.skipTest(err)

        result = umu_util._fsck_path(Path(gettempdir()), filesystem)
        self.assertTrue(isinstance(result, bool), f"Expected '{result}' to be a bool")

    def test_get_tempdir(self):
        """Test get_tempdir.

        Expects a Path to be returned.
        """
        result = None

        # Skip this test if /proc does not exist
        if not Path("/proc").exists():
            err = "/proc does not exists"
            self.skipTest(err)

        result = umu_util.get_tempdir(Path(gettempdir()))
        self.assertTrue(isinstance(result, Path), f"Expected '{result}' to be a Path")

    def test_fetch_patch_url_req(self):
        """Test _fetch_patch when the second request fails.

        Expects an empty byte string.
        """
        result = None
        expected = "bar"
        mock_gh_release = {
            "assets": [
                {"name": "GE-Latest.cbor", "browser_download_url": "foo"},
                {"name": "UMU-Latest.cbor", "browser_download_url": "foo"},
            ]
        }

        if find_spec("cbor2") is None or find_spec("xxhash") is None:
            err = "delta dependencies not installed"
            self.skipTest(err)

        os.environ["PROTONPATH"] = "GE-Latest"

        # Mock the response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json.return_value = mock_gh_release
        mock_resp.data = expected

        # Mock 2nd response
        mock_resp2 = MagicMock()
        mock_resp2.status = 400
        mock_resp2.json.return_value = mock_gh_release
        mock_resp2.data = expected

        # Mock the thread pool
        mock_tp = MagicMock()

        # Mock the call to http pool
        mock_hp = MagicMock()
        mock_hp.request.side_effect = [mock_resp, mock_resp2]

        result = umu_proton._fetch_patch((mock_tp, mock_hp))
        self.assertEqual(b"", result, f"Expected {expected}, receieved {result}")

        # UMU-Latest codename
        result = None
        os.environ["PROTONPATH"] = "UMU-Latest"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json.return_value = mock_gh_release
        mock_resp.data = expected

        mock_resp2 = MagicMock()
        mock_resp2.status = 400
        mock_resp2.json.return_value = mock_gh_release
        mock_resp2.data = expected

        mock_tp = MagicMock()

        mock_hp = MagicMock()
        mock_hp.request.side_effect = [mock_resp, mock_resp2]

        result = umu_proton._fetch_patch((mock_tp, mock_hp))
        self.assertEqual(b"", result, f"Expected {expected}, receieved {result}")

    def test_fetch_patch(self):
        """Test _fetch_patch on success.

        Expects a non-empty byte string to be returned. In practice, the return
        value is the CBOR data.
        """
        result = None
        expected = "bar"
        mock_gh_release = {
            "assets": [
                {"name": "GE-Latest.cbor", "browser_download_url": "foo"},
                {"name": "UMU-Latest.cbor", "browser_download_url": "foo"},
            ]
        }

        if find_spec("cbor2") is None or find_spec("xxhash") is None:
            err = "delta dependencies not installed"
            self.skipTest(err)

        os.environ["PROTONPATH"] = "GE-Latest"

        # Mock the response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json.return_value = mock_gh_release
        mock_resp.data = expected

        # Mock the thread pool
        mock_tp = MagicMock()

        # Mock the call to http pool
        mock_hp = MagicMock()
        mock_hp.request.return_value = mock_resp

        result = umu_proton._fetch_patch((mock_tp, mock_hp))
        self.assertEqual(expected, result, f"Expected {expected}, receieved {result}")

        # UMU-Latest codename
        result = None
        os.environ["PROTONPATH"] = "UMU-Latest"

        result = umu_proton._fetch_patch((mock_tp, mock_hp))
        self.assertEqual(expected, result, f"Expected {expected}, receieved {result}")

    def test_fetch_patch_no_names(self):
        """Test _fetch_patch for invalid GitHub assets.

        Expects empty byte string to be returned when unable to find
        assets that do not have a .cbor suffix or do not begin with a
        codename (e.g., GE-Latest).
        """
        result = None
        mock_gh_release = {
            "assets": [
                {"name": "", "browser_download_url": "foo"},
                {"name": "", "browser_download_url": ""},
            ]
        }

        if find_spec("cbor2") is None or find_spec("xxhash") is None:
            err = "delta dependencies not installed"
            self.skipTest(err)

        os.environ["PROTONPATH"] = "GE-Latest"

        # Mock the response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json.return_value = mock_gh_release

        # Mock the thread pool
        mock_tp = MagicMock()

        # Mock the call to http pool
        mock_hp = MagicMock()
        mock_hp.request.return_value = mock_resp

        result = umu_proton._fetch_patch((mock_tp, mock_hp))
        self.assertEqual(b"", result, f"Expected empty bytes, receieved {result}")

        # UMU-Latest codename
        result = None
        os.environ["PROTONPATH"] = "UMU-Latest"

        result = umu_proton._fetch_patch((mock_tp, mock_hp))
        self.assertEqual(b"", result, f"Expected empty bytes, receieved {result}")

    def test_fetch_patch_none(self):
        """Test _fetch_patch on request failure.

        Expects an empty byte string.
        """
        result = None
        mock_gh_release = {
            "assets": [
                {"name": "", "browser_download_url": ""},
                {"name": "", "browser_download_url": ""},
            ]
        }

        if find_spec("cbor2") is None or find_spec("xxhash") is None:
            err = "delta dependencies not installed"
            self.skipTest(err)

        os.environ["PROTONPATH"] = "GE-Latest"

        # Mock the failed response
        mock_resp = MagicMock()
        mock_resp.status = 404
        mock_resp.json.return_value = mock_gh_release

        # Mock the thread pool
        mock_tp = MagicMock()

        # Mock the call to http pool
        mock_hp = MagicMock()
        mock_hp.request.return_value = mock_resp

        result = umu_proton._fetch_patch((mock_tp, mock_hp))
        self.assertEqual(b"", result, f"Expected empty bytes, receieved {result}")

        # UMU-Latest codename
        result = None
        os.environ["PROTONPATH"] = "UMU-Latest"

        result = umu_proton._fetch_patch((mock_tp, mock_hp))
        self.assertEqual(b"", result, f"Expected empty bytes, receieved {result}")

    def test_fetch_patch_missing_deps(self):
        """Test _fetch_patch when optional deps are missing.

        Expects an empty byte string.
        """
        result = None
        os.environ["PROTONPATH"] = "GE-Latest"

        if find_spec("cbor2") is None or find_spec("xxhash") is None:
            err = "delta dependencies not installed"
            self.skipTest(err)

        with patch.object(umu_proton, "find_spec", return_value=False):
            result = umu_proton._fetch_patch(self.test_session_pools)
        self.assertEqual(b"", result, f"Expected empty bytes, receieved {result}")

        # UMU-Latest codename
        result = None
        os.environ["PROTONPATH"] = "UMU-Latest"

        with patch.object(umu_proton, "find_spec", return_value=False):
            result = umu_proton._fetch_patch(self.test_session_pools)
        self.assertEqual(b"", result, f"Expected empty bytes, receieved {result}")

    def test_fetch_patch_no_latest(self):
        """Test _fetch_patch when PROTONPATH is not set or invalid.

        Expects an empty byte string.
        """
        result = None

        # PROTONPATH unset
        if find_spec("cbor2") is None or find_spec("xxhash") is None:
            err = "delta dependencies not installed"
            self.skipTest(err)
        result = umu_proton._fetch_patch(self.test_session_pools)
        self.assertEqual(b"", result, f"Expected empty bytes, receieved {result}")

        # PROTONPATH set
        result = None
        os.environ["PROTONPATH"] = "foo-Latest"
        result = umu_proton._fetch_patch(self.test_session_pools)
        self.assertEqual(b"", result, f"Expected empty bytes, receieved {result}")

    def test_get_delta_invalid_sig(self):
        """Test get_delta when patch signature is invalid."""
        mock_assets = (("foo", "foo"), ("foo.tar.gz", "foo"))
        os.environ["PROTONPATH"] = umu_proton.ProtonVersion.UMULatest.value
        result = None

        # If either cbor2 or the Rust module DNE, skip
        try:
            from cbor2 import dumps
        except ModuleNotFoundError:
            err = "python3-cbor2 not installed"
            self.skipTest(err)

        if find_spec("umu_delta") is None:
            err = "umu_delta module not compiled"
            self.skipTest(err)

        mock_patch = dumps(
            {
                "public_key": ["foo", "bar"],
                "signature": [b"bar", b"foo"],
                "contents": ["baz"],
            }
        )
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=None)

        self.test_umu_compat.joinpath(os.environ["PROTONPATH"]).mkdir(exist_ok=True)
        self.test_umu_compat.joinpath(
            os.environ["PROTONPATH"], "compatibilitytool.vdf"
        ).touch(exist_ok=True)

        # When the value within the vdf file and GH asset Proton value differ, we update.
        # Change the value here, to simulate a latest update scenario
        self.test_umu_compat.joinpath(
            os.environ["PROTONPATH"], "compatibilitytool.vdf"
        ).write_text("bar")

        with (
            patch.object(umu_proton, "unix_flock", return_value=mock_ctx),
            patch("umu.umu_delta.valid_key", lambda _: True),
        ):
            result = umu_proton._get_delta(
                self.env,
                self.test_umu_compat,
                mock_patch,
                mock_assets,
                self.test_session_pools,
            )

        self.assertTrue(result is None, f"Expected None, received {result}")

    def test_get_delta_invalid_key(self):
        """Test get_delta when public key is invalid."""
        mock_assets = (("foo", "foo"), ("foo.tar.gz", "foo"))
        os.environ["PROTONPATH"] = umu_proton.ProtonVersion.UMULatest.value
        result = None

        # If either cbor2 or the Rust module DNE, skip
        try:
            from cbor2 import dumps
        except ModuleNotFoundError:
            err = "python3-cbor2 not installed"
            self.skipTest(err)

        if find_spec("umu_delta") is None:
            err = "umu_delta module not compiled"
            self.skipTest(err)

        mock_patch = dumps({"public_key": ["foo", "bar"]})
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=None)

        self.test_umu_compat.joinpath(os.environ["PROTONPATH"]).mkdir(
            parents=True, exist_ok=True
        )

        self.test_umu_compat.joinpath(
            os.environ["PROTONPATH"], "compatibilitytool.vdf"
        ).touch(exist_ok=True)

        # When the value within the vdf file and GH asset Proton value differ, we update.
        # Change the value here, to simulate a latest update scenario
        self.test_umu_compat.joinpath(
            os.environ["PROTONPATH"], "compatibilitytool.vdf"
        ).write_text("bar")

        with patch.object(umu_proton, "unix_flock", return_value=mock_ctx):
            result = umu_proton._get_delta(
                self.env,
                self.test_umu_compat,
                mock_patch,
                mock_assets,
                self.test_session_pools,
            )

        self.assertTrue(result is None, f"Expected None, received {result}")

    def test_get_delta_check_update(self):
        """Test get_delta when checking if latest is installed."""
        mock_assets = (("foo", "foo"), ("foo.tar.gz", "foo"))
        os.environ["PROTONPATH"] = umu_proton.ProtonVersion.UMULatest.value
        result = None

        # If either cbor2 or the Rust module DNE, skip
        try:
            from cbor2 import dumps
        except ModuleNotFoundError:
            err = "python3-cbor2 not installed"
            self.skipTest(err)

        if find_spec("umu_delta") is None:
            err = "umu_delta module not compiled"
            self.skipTest(err)

        mock_patch = dumps({"foo": "foo"})
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=None)

        self.test_umu_compat.joinpath(os.environ["PROTONPATH"]).mkdir(
            parents=True, exist_ok=True
        )

        self.test_umu_compat.joinpath(
            os.environ["PROTONPATH"], "compatibilitytool.vdf"
        ).touch(exist_ok=True)

        self.test_umu_compat.joinpath(
            os.environ["PROTONPATH"], "compatibilitytool.vdf"
        ).write_text("foo")

        with patch.object(umu_proton, "unix_flock", return_value=mock_ctx):
            result = umu_proton._get_delta(
                self.env,
                self.test_umu_compat,
                mock_patch,
                mock_assets,
                self.test_session_pools,
            )

        self.assertTrue(result is self.env, f"Expected None, received {result}")

        mock_val = str(
            self.test_umu_compat.joinpath(umu_proton.ProtonVersion.UMULatest.value)
        )
        self.assertEqual(
            os.environ["PROTONPATH"],
            mock_val,
            f"Expected {mock_val}, received {os.environ['PROTONPATH']}",
        )
        self.assertEqual(
            self.env["PROTONPATH"],
            mock_val,
            f"Expected {mock_val}, received {self.env['PROTONPATH']}",
        )

    def test_get_delta_cbor(self):
        """Test get_delta when parsing CBOR."""
        mock_assets = (("foo", "foo"), ("foo.tar.gz", "foo"))
        os.environ["PROTONPATH"] = umu_proton.ProtonVersion.UMULatest.value

        # If either cbor2 or the Rust module DNE, skip
        try:
            from cbor2 import dumps
        except ModuleNotFoundError:
            err = "python3-cbor2 not installed"
            self.skipTest(err)

        if find_spec("umu_delta") is None:
            err = "umu_delta module not compiled"
            self.skipTest(err)

        mock_patch = dumps({"foo": "foo"})
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=None)

        self.test_umu_compat.joinpath(os.environ["PROTONPATH"]).mkdir(
            parents=True, exist_ok=True
        )

        with patch.object(umu_proton, "unix_flock", return_value=mock_ctx):
            result = umu_proton._get_delta(
                self.env,
                self.test_umu_compat,
                mock_patch,
                mock_assets,
                self.test_session_pools,
            )
            self.assertTrue(result is None, f"Expected None, received {result}")

    def test_get_delta_cbor_err(self):
        """Test get_delta when parsing invalid CBOR."""
        mock_patch = b"foo"
        mock_assets = (("foo", "foo"), ("foo", "foo"))
        os.environ["PROTONPATH"] = umu_proton.ProtonVersion.UMULatest.value

        if find_spec("cbor2") is None:
            err = "umu_delta module not compiled"
            self.skipTest(err)

        if find_spec("umu_delta") is None:
            err = "umu_delta module not compiled"
            self.skipTest(err)

        result = umu_proton._get_delta(
            self.env,
            self.test_umu_compat,
            mock_patch,
            mock_assets,
            self.test_session_pools,
        )
        self.assertTrue(result is None, f"Expected None, received {result}")

    def test_get_delta_no_latest(self):
        """Test get_delta when parsing invalid CBOR."""
        mock_patch = b"foo"
        mock_assets = (("foo", "foo"), ("foo", "foo"))
        # Empty string is not a valid code name
        os.environ["PROTONPATH"] = ""

        result = umu_proton._get_delta(
            self.env,
            self.test_umu_compat,
            mock_patch,
            mock_assets,
            self.test_session_pools,
        )
        self.assertTrue(result is None, f"Expected None, received {result}")

    def test_get_delta_no_patch(self):
        """Test get_delta for empty or absent patch data."""
        mock_patch = b""
        mock_assets = (("foo", "foo"), ("foo", "foo"))
        os.environ["PROTONPATH"] = umu_proton.ProtonVersion.UMULatest.value

        result = umu_proton._get_delta(
            self.env,
            self.test_umu_compat,
            mock_patch,
            mock_assets,
            self.test_session_pools,
        )
        self.assertTrue(result is None, f"Expected None, received {result}")

    def test_get_delta_no_assets(self):
        """Test get_delta when no GH assets are returned."""
        mock_patch = b""
        mock_assets = ()

        result = umu_proton._get_delta(
            self.env,
            self.test_umu_compat,
            mock_patch,
            mock_assets,
            self.test_session_pools,
        )
        self.assertTrue(result is None, f"Expected None, received {result}")

    def test_main_nomusl(self):
        """Test __main__.main to ensure an exit when on a musl-based system."""
        os.environ["LD_LIBRARY_PATH"] = f"{os.environ['LD_LIBRARY_PATH']}:musl"
        with (
            patch.object(
                __main__,
                "parse_args",
                return_value=["foo", "foo"],
            ),
            self.assertRaises(SystemExit),
        ):
            __main__.main()

    def test_main_noroot(self):
        """Test __main__.main to ensure an exit when run as a privileged user."""
        with (
            patch.object(
                __main__,
                "parse_args",
                return_value=["foo", "foo"],
            ),
            self.assertRaises(SystemExit),
            patch.object(os, "geteuid", return_value=0),
        ):
            __main__.main()

    def test_restore_umu_cb_false(self):
        """Test _restore_umu when the callback evaluates to False."""
        mock_cb = Mock(return_value=False)
        result = MagicMock()

        with (
            TemporaryDirectory() as file,
            patch.object(umu_runtime, "_install_umu"),
        ):
            mock_subdir = Path(file).joinpath("steamrt3")
            mock_subdir.mkdir(parents=True, exist_ok=True)
            mock_runtime_ver = ("sniper", "steamrt3", "1628350")
            mock_session_pools = (MagicMock(), MagicMock())
            result = umu_runtime._restore_umu(
                mock_subdir, mock_runtime_ver, mock_session_pools, mock_cb
            )
            self.assertTrue(result is None, f"Expected None, received {result}")
            self.assertTrue(
                mock_cb.mock_calls,
                "Expected callback to be called",
            )

    def test_restore_umu(self):
        """Test _restore_umu."""
        mock_cb = Mock(return_value=True)
        result = MagicMock()

        with TemporaryDirectory() as file:
            mock_subdir = Path(file).joinpath("steamrt3")
            mock_subdir.mkdir(parents=True, exist_ok=True)
            mock_runtime_ver = ("sniper", "steamrt3", "1628350")
            mock_session_pools = (MagicMock(), MagicMock())
            result = umu_runtime._restore_umu(
                mock_subdir, mock_runtime_ver, mock_session_pools, mock_cb
            )
            self.assertTrue(result is None, f"Expected None, received {result}")
            self.assertTrue(
                mock_cb.mock_calls,
                "Expected callback to be called",
            )

    def test_setup_umu_update(self):
        """Test setup_umu when updating the runtime."""
        result = MagicMock()

        # Mock a new install
        with TemporaryDirectory() as file:
            # Populate our fake $XDG_DATA_HOME/umu
            mock_subdir = Path(file, self.test_runtime_default[1])
            mock_subdir.mkdir()
            mock_subdir.joinpath("umu").touch()
            # Mock the runtime ver
            mock_runtime_ver = ("sniper", "steamrt3", "1628350")
            # Mock our thread and conn pool
            mock_session_pools = (MagicMock(), MagicMock())
            with patch.object(umu_runtime, "_update_umu"):
                result = umu_runtime.setup_umu(
                    mock_subdir,
                    mock_runtime_ver,
                    mock_session_pools,
                )
            self.assertTrue(result is None, f"Expected None, received {result}")

    def test_setup_umu_noupdate(self):
        """Test setup_umu when setting runtime updates are disabled."""
        result = MagicMock()
        os.environ["UMU_RUNTIME_UPDATE"] = "0"

        # Mock a new install
        with TemporaryDirectory() as file:
            # Populate our fake $XDG_DATA_HOME/umu
            mock_subdir = Path(file, self.test_runtime_default[1])
            mock_subdir.mkdir()
            mock_subdir.joinpath("umu").touch()
            # Mock the runtime ver
            mock_runtime_ver = ("sniper", "steamrt3", "1628350")
            # Mock our thread and conn pool
            mock_session_pools = (MagicMock(), MagicMock())
            with patch.object(umu_runtime, "_restore_umu"):
                result = umu_runtime.setup_umu(
                    mock_subdir,
                    mock_runtime_ver,
                    mock_session_pools,
                )
            self.assertTrue(result is None, f"Expected None, received {result}")

    def test_setup_umu(self):
        """Test setup_umu on new install."""
        result = MagicMock()

        # Mock a new install
        with TemporaryDirectory() as file:
            mock_subdir = Path(file, self.test_runtime_default[1])
            mock_subdir.mkdir()
            mock_subdir.joinpath("umu").touch()
            # Mock the runtime ver
            mock_runtime_ver = ("sniper", "steamrt3", "1628350")
            # Mock our thread and conn pool
            mock_session_pools = (MagicMock(), MagicMock())
            with patch.object(umu_runtime, "_restore_umu"):
                result = umu_runtime.setup_umu(
                    mock_subdir,
                    mock_runtime_ver,
                    mock_session_pools,
                )
            self.assertTrue(result is None, f"Expected None, received {result}")

    def test_write_file_chunks_none(self):
        """Test write_file_chunks when not passing a chunk size."""
        with NamedTemporaryFile() as file1, TemporaryFile("rb+") as file2:
            chunk_size = 8
            mock_file = Path(file1.name)
            hasher = hashlib.blake2b()
            file2.write(os.urandom(chunk_size))
            # Pass a buffered reader as our fake http response
            umu_util.write_file_chunks(mock_file, file2, hasher)
            self.assertTrue(hasher.digest(), "Expected hashed data > 0, received 0")

    def test_write_file_chunks(self):
        """Test write_file_chunks."""
        with NamedTemporaryFile() as file1, TemporaryFile("rb+") as file2:
            chunk_size = 8
            mock_file = Path(file1.name)
            hasher = hashlib.blake2b()
            file2.write(os.urandom(chunk_size))
            # Pass a buffered reader as our fake http response
            umu_util.write_file_chunks(mock_file, file2, hasher, chunk_size)
            self.assertTrue(hasher.digest(), "Expected hashed data > 0, received 0")

    def test_get_gamescope_baselayer_appid_err(self):
        """Test get_gamescope_baselayer_appid on error.

        Expects function be fail safe, handling any exceptions when getting
        GAMESCOPECTRL_BASELAYER_APPID
        """
        mock_display = MagicMock(spec=Display)
        mock_display.screen.side_effect = DisplayConnectionError(mock_display, "foo")

        result = umu_run.get_gamescope_baselayer_appid(mock_display)
        self.assertTrue(result is None, f"Expected a value, received: {result}")

    def test_get_gamescope_baselayer_appid(self):
        """Test get_gamescope_baselayer_appid."""
        mock_display = MagicMock(spec=Display)
        mock_screen = MagicMock()
        mock_root = MagicMock()
        mock_prop = MagicMock()
        result = None

        mock_display.screen.return_value = mock_screen
        mock_display.get_atom.return_value = 0
        mock_screen.root = mock_root
        mock_root.get_full_property.return_value = mock_prop
        mock_prop.value = array("I", [1, 2, 3])

        result = umu_run.get_gamescope_baselayer_appid(mock_display)
        self.assertTrue(result == [1, 2, 3], f"Expected a value, received: {result}")

    def test_set_steam_game_property_err(self):
        """Test set_steam_game_property on error.

        Expects function be fail safe, handling any exceptions when setting
        a new value for STEAM_GAME.
        """
        mock_display = MagicMock(spec=Display)
        mock_window_ids = {"1", "2", "3"}
        mock_appid = 123

        mock_display.create_resource_object.side_effect = DisplayConnectionError(
            mock_display, "foo"
        )

        result = umu_run.set_steam_game_property(
            mock_display, mock_window_ids, mock_appid
        )

        self.assertTrue(result is mock_display, f"Expected Display, received: {result}")
        mock_display.create_resource_object.assert_called()

    def test_set_steam_game_property(self):
        """Test set_steam_game_property."""
        mock_display = MagicMock(spec=Display)
        mock_window = MagicMock(spec=Window)
        mock_window_ids = {"1", "2", "3"}
        mock_appid = 123

        mock_display.create_resource_object.return_value = mock_window
        mock_display.get_atom.return_value = 0

        result = umu_run.set_steam_game_property(
            mock_display, mock_window_ids, mock_appid
        )
        self.assertTrue(result is mock_display, f"Expected Display, received: {result}")
        mock_display.create_resource_object.assert_called()
        mock_display.get_atom.assert_called()

    def test_get_window_ids_err(self):
        """Test get_window_ids on error.

        Expects function to be fail safe, so any exceptions should be handled
        when returning child windows.
        """
        mock_display = MagicMock(spec=Display)
        mock_event = MagicMock(spec=Event)
        mock_screen = MagicMock()
        mock_root = MagicMock()
        mock_query_tree = MagicMock()

        mock_event.type = CreateNotify
        mock_display.next_event.return_value = mock_event

        mock_display.screen.return_value = mock_screen
        mock_screen.root = mock_root
        mock_root.query_tree.side_effect = DisplayConnectionError(mock_display, "foo")
        mock_query_tree.children = set()

        result = umu_run.get_window_ids(mock_display)

        # Assertions
        self.assertTrue(result is None, f"Expected None, received: {result}")
        mock_display.next_event.assert_called_once()
        mock_display.screen.assert_called_once()
        mock_screen.root.query_tree.assert_called_once()

    def test_get_window_ids(self):
        """Test get_window_ids."""
        mock_display = MagicMock(spec=Display)
        mock_event = MagicMock(spec=Event)
        mock_screen = MagicMock()
        mock_root = MagicMock()
        mock_query_tree = MagicMock()

        mock_event.type = CreateNotify
        mock_display.next_event.return_value = mock_event

        mock_display.screen.return_value = mock_screen
        mock_screen.root = mock_root
        mock_root.query_tree.return_value = mock_query_tree
        mock_query_tree.children = set()

        result = umu_run.get_window_ids(mock_display)

        self.assertTrue(isinstance(result, set), f"Expected a set, received: {result}")
        mock_display.next_event.assert_called_once()
        mock_display.screen.assert_called_once()
        mock_screen.root.query_tree.assert_called_once()

    def test_get_steam_layer_id(self):
        """Test get_steam_layer_id.

        An IndexError and a ValueError should be handled when
        Steam environment variables are empty values or non-integers.
        """
        os.environ["STEAM_COMPAT_TRANSCODED_MEDIA_PATH"] = ""
        os.environ["STEAM_COMPAT_MEDIA_PATH"] = "foo"
        os.environ["STEAM_FOSSILIZE_DUMP_PATH"] = "bar"
        os.environ["DXVK_STATE_CACHE_PATH"] = "baz"
        result = umu_run.get_steam_appid(os.environ)

        self.assertEqual(
            result,
            0,
            "Expected 0 when Steam environment variables are empty or non-int",
        )

    def test_create_shim_exe(self):
        """Test create_shim and ensure it's executable."""
        shim = None

        with TemporaryDirectory() as tmp:
            shim = Path(tmp, "umu-shim")
            umu_runtime.create_shim(shim)
            self.assertTrue(
                os.access(shim, os.X_OK), f"Expected '{shim}' to be executable"
            )

    def test_create_shim(self):
        """Test create_shim."""
        shim = None

        with TemporaryDirectory() as tmp:
            shim = Path(tmp, "umu-shim")
            umu_runtime.create_shim(shim)
            self.assertTrue(shim.is_file(), f"Expected '{shim}' to be a file")
            # Ensure there's data
            self.assertTrue(shim.stat().st_size > 0, f"Expected '{shim}' to have data")

    def test_run_command(self):
        """Test run_command."""
        mock_exe = "foo"
        mock_command = (
            "/home/foo/.local/share/umu/umu",
            "--verb",
            "waitforexitandrun",
            "--",
            "/home/foo/.local/share/Steam/compatibilitytools.d/GE-Proton9-7/proton",
            mock_exe,
        )
        libc = umu_util.get_libc()

        # Skip this test if libc is not found in system
        if not libc:
            return

        os.environ["EXE"] = mock_exe
        with (
            patch.object(
                umu_run,
                "Popen",
            ) as mock_popen,
        ):
            mock_proc = MagicMock()
            mock_proc.__enter__.return_value = mock_proc
            mock_proc.wait.return_value = 0
            mock_proc.pid = 1234
            mock_popen.return_value = mock_proc
            result = umu_run.run_command(mock_command)
            mock_popen.assert_called_once()
            self.assertEqual(
                result,
                0,
                "Expected 0 status code",
            )

    def test_run_command_none(self):
        """Test run_command when passed an empty tuple or None."""
        with self.assertRaises(ValueError):
            umu_run.run_command(())
            umu_run.run_command(None)

    def test_get_libc(self):
        """Test get_libc."""
        self.assertIsInstance(umu_util.get_libc(), str, "Value is not a string")

    def test_is_installed_verb_noverb(self):
        """Test is_installed_verb when passed an empty verb."""
        verb = []

        with self.assertRaises(ValueError):
            umu_util.is_installed_verb(verb, self.test_winepfx)

    def test_is_installed_verb_nopfx(self):
        """Test is_installed_verb when passed a non-existent pfx."""
        verb = ["foo"]
        result = True

        # Handle the None type
        # In the real usage, this should not happen
        with self.assertRaises(FileNotFoundError):
            umu_util.is_installed_verb(verb, None)

        # An exception should not be raised for a non-existent directory. When
        # the prefix does not exist, umu will create the default prefix as
        # ~/Games/umu/$GAMEID and will be created by Proton.
        result = umu_util.is_installed_verb(verb, Path("./foo"))
        self.assertFalse(result, "wine prefix exists")

    def test_is_installed_verb_nofile(self):
        """Test is_installed_verb when the log file is absent."""
        verb = ["foo"]
        result = True

        result = umu_util.is_installed_verb(verb, self.test_winepfx)
        self.assertFalse(result, "winetricks.log file was found")

    def test_is_installed_verb(self):
        """Test is_installed_verb.

        Reads the winetricks.log file within the wine prefix to find the verb
        that was passed from the command line.
        """
        verbs = ["foo", "bar"]
        wt_log = self.test_winepfx.joinpath("winetricks.log")
        result = False

        wt_log.write_text("\n".join(verbs))
        result = umu_util.is_installed_verb(verbs, self.test_winepfx)
        self.assertTrue(result, "winetricks verb was not installed")

    def test_is_not_winetricks_verb(self):
        """Test is_winetricks_verb when not passed a valid verb."""
        verbs = ["--help", ";bash", "list-all"]
        result = False

        result = umu_util.is_winetricks_verb(verbs)
        self.assertFalse(result, f"{verbs} contains a winetricks verb")

        # Handle None and empty cases
        result = umu_util.is_winetricks_verb(None)
        self.assertFalse(result, f"{verbs} contains a winetricks verb")

        result = umu_util.is_winetricks_verb([])
        self.assertFalse(result, f"{verbs} contains a winetricks verb")

    def test_is_winetricks_verb(self):
        """Test is_winetricks_verb when passed valid verbs.

        Expects winetricks verbs to follow ^[a-zA-Z_0-9]+(=[a-zA-Z0-9]*)?$.
        """
        verbs = []
        result = True
        verbs_file = Path(__file__).parent.joinpath(
            "../", "tests", "testdata", "winetricks_verbs.txt"
        )

        with verbs_file.open(mode="r", encoding="utf-8") as file:
            verbs = [line.strip() for line in file]

        result = umu_util.is_winetricks_verb(verbs)
        self.assertTrue(result, f"Expected {verbs} to only contain winetricks verbs")

    def test_check_runtime(self):
        """Test check_runtime when pv-verify does not exist.

        check_runtime calls pv-verify to verify the integrity of the runtime
        archive's contents, and will only be called when restoring or setting
        up the runtime

        If the pv-verify binary does not exist, a warning should be logged and
        the function should return
        """
        self.test_user_share.joinpath("pressure-vessel", "bin", "pv-verify").unlink()
        result = umu_runtime.check_runtime(
            self.test_user_share, self.test_runtime_default
        )
        self.assertEqual(result, 1, "Expected the exit code 1")

    def test_check_runtime_success(self):
        """Test check_runtime when runtime validation succeeds."""
        mock = CompletedProcess(["foo"], 0)
        with patch.object(umu_runtime, "run", return_value=mock):
            result = umu_runtime.check_runtime(
                self.test_user_share, self.test_runtime_default
            )
            self.assertEqual(result, 0, "Expected the exit code 0")

    def test_check_runtime_dir(self):
        """Test check_runtime when passed a BUILD_ID that does not exist."""
        runtime = Path(self.test_user_share, "sniper_platform_0.20240125.75305")

        # Mock the removal of the runtime directory
        # In the real usage when updating the runtime, this should not happen
        # since the runtime validation will occur directly after extracting
        # the contents to $HOME/.local/share/umu
        if runtime.is_dir():
            rmtree(runtime.as_posix())

        mock = CompletedProcess(["foo"], 1)
        with patch.object(umu_runtime, "run", return_value=mock):
            result = umu_runtime.check_runtime(
                self.test_user_share, self.test_runtime_default
            )
            self.assertEqual(result, 1, "Expected the exit code 1")

    def test_fetch_releases_no_assets(self):
        """Test _fetch_releases for unexpected values.

        Expects a Github asset's name field to have the suffix '.tar.gz' and
        the prefix 'UMU-Proton' or 'GE-Proton'. Or the name field to have 'sum'
        suffix, for the digest file.

        A tuple should always be returned. Otherwise, it indicates that Github
        has changed its API or we had change file names. An exception should
        never be raised.
        """
        result = None
        mock_gh_release = {
            "assets": [
                {
                    "name": "foo",
                    "browser_download_url": "",
                },
                {
                    "name": "bar",
                    "browser_download_url": "",
                },
            ]
        }
        # Mock the call to urlopen
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json.return_value = mock_gh_release

        # Mock thread pool
        mock_tp = MagicMock()

        # Mock conn pool
        mock_hp = MagicMock()
        mock_hp.request.return_value = mock_resp

        # Mock PROTONPATH="", representing a download to UMU-Proton
        os.environ["PROTONPATH"] = ""

        result = umu_proton._fetch_releases((mock_tp, mock_hp))
        self.assertTrue(result is not None, "Expected a value, received None")
        self.assertTrue(isinstance(result, tuple), f"Expected tuple, received {result}")
        result_len = len(result)
        self.assertFalse(
            result_len,
            f"Expected tuple with no len, received len {result_len}",
        )

    def test_fetch_releases(self):
        """Test _fetch_releases."""
        result = None
        mock_gh_release = {
            "assets": [
                {
                    "name": "sum",
                    "browser_download_url": "",
                },
                {
                    "name": "UMU-Proton.tar.gz",
                    "browser_download_url": "",
                },
            ]
        }

        # Mock the response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json.return_value = mock_gh_release
        # Mock our thread and http pools

        # Mock the thread pool
        mock_tp = MagicMock()

        # Mock the call to http pool
        mock_hp = MagicMock()
        mock_hp.request.return_value = mock_resp

        # Mock PROTONPATH="", representing a download to UMU-Proton
        os.environ["PROTONPATH"] = ""

        result = umu_proton._fetch_releases((mock_tp, mock_hp))
        self.assertTrue(result is not None, "Expected a value, received None")
        self.assertTrue(isinstance(result, tuple), f"Expected tuple, received {result}")
        result_len = len(result)
        self.assertTrue(
            result_len,
            f"Expected tuple with len, received len {result_len}",
        )

    def test_ge_proton(self):
        """Test check_env when the code name GE-Proton is set for PROTONPATH.

        Tests the case when the user has no internet connection or GE-Proton
        wasn't found in local system.
        """
        test_archive = self.test_archive.rename("GE-Proton9-2.tar.gz")
        umu_util.extract_tarfile(test_archive, test_archive.parent)

        with (
            self.assertRaises(FileNotFoundError),
            patch.object(umu_proton, "_fetch_releases", return_value=None),
            patch.object(umu_proton, "_get_latest", return_value=None),
            patch.object(umu_proton, "_get_from_compat", return_value=None),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["PROTONPATH"] = "GE-Proton"
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(
                result_env, self.test_session_pools, download=result_dl
            )
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
        mock_session_pools = (MagicMock(), MagicMock())
        with (
            self.assertRaises(FileNotFoundError),
            patch.object(umu_proton, "_fetch_releases", return_value=None),
            patch.object(umu_proton, "_get_latest", return_value=None),
            patch.object(umu_proton, "_get_from_compat", return_value=None),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["PROTONPATH"] = "GE-Proton"
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, mock_session_pools, download=result_dl)
            self.assertFalse(os.environ.get("PROTONPATH"), "Expected empty string")

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
        files = (("", ""), (self.test_archive.name, ""))
        tmpdirs = (self.test_cache, self.test_cache_home)
        compats = (self.test_umu_compat, self.test_compat)

        # Mock the context manager object that creates the file lock
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=None)

        with (
            patch("umu.umu_proton._fetch_proton") as mock_function,
            ThreadPoolExecutor(),
            patch.object(umu_proton, "unix_flock", return_value=mock_ctx),
        ):
            # Mock the interrupt
            # We want the dir we tried to extract to be cleaned
            mock_function.side_effect = KeyboardInterrupt
            result = umu_proton._get_latest(
                self.env,
                compats,
                tmpdirs,
                files,
                self.test_session_pools,
            )
            self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to be empty")
            self.assertFalse(result, "Expected None on KeyboardInterrupt")

    def test_latest_val_err(self):
        """Test _get_latest when something goes wrong when downloading Proton.

        Assumes a file is being downloaded in this case

        A ValueError should be raised, and one case it can happen is if the
        digests mismatched for some reason
        """
        result = None
        # In the real usage, should be populated after successful callout for
        # latest Proton releases
        # When empty, it means the callout failed for some reason (e.g. no
        # internet)
        files = (("", ""), (self.test_archive.name, ""))
        tmpdirs = (self.test_cache, self.test_cache_home)
        compats = (self.test_umu_compat, self.test_compat)

        # Mock the context manager object that creates the file lock
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=None)

        self.assertTrue(
            self.test_archive.is_file(),
            "Expected test file in cache to exist",
        )

        with (
            patch("umu.umu_proton._fetch_proton") as mock_function,
            ThreadPoolExecutor(),
            patch.object(umu_proton, "unix_flock", return_value=mock_ctx),
        ):
            # Mock the interrupt
            mock_function.side_effect = ValueError
            result = umu_proton._get_latest(
                self.env,
                compats,
                tmpdirs,
                files,
                self.test_session_pools,
            )
            self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to be empty")
            self.assertFalse(result, "Expected None when a ValueError occurs")

    def test_latest_offline(self):
        """Test _get_latest when the user doesn't have internet."""
        result = None
        # In the real usage, should be populated after successful callout for
        # latest Proton releases
        # When empty, it means the callout failed for some reason (e.g. no
        # internet)
        files = ()
        tmpdirs = (self.test_cache, self.test_cache_home)
        compats = (self.test_umu_compat, self.test_compat)

        # Mock the context manager object that creates the file lock
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=None)

        os.environ["PROTONPATH"] = ""

        with (
            patch("umu.umu_proton._fetch_proton"),
            ThreadPoolExecutor(),
            patch.object(umu_proton, "unix_flock", return_value=mock_ctx),
        ):
            result = umu_proton._get_latest(
                self.env,
                compats,
                tmpdirs,
                files,
                self.test_session_pools,
            )
            self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to be empty")
            self.assertFalse(result, "Expected None to be returned from _get_latest")

    def test_latest_umu(self):
        """Test _get_latest when online and when an empty PROTONPATH is set.

        Tests that the latest UMU-Proton was set to PROTONPATH and old
        stable versions were removed in the process.
        """
        result = None
        latest = Path("UMU-Proton-9.0-beta16")
        latest.mkdir()
        Path(f"{latest}.sha512sum").touch()
        files = ((f"{latest}.sha512sum", ""), (f"{latest}.tar.gz", ""))
        tmpdirs = (self.test_cache, self.test_cache_home)
        compats = (self.test_umu_compat, self.test_compat)

        # Mock the context manager object that creates the file lock
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=None)
        mock_ctx.__exit__ = MagicMock(return_value=None)

        # Mock the latest Proton in /tmp
        test_archive = self.test_cache.joinpath(f"{latest}.tar.gz")
        with tarfile.open(test_archive.as_posix(), "w:gz") as tar:
            tar.add(latest.as_posix(), arcname=latest.as_posix())

        # Add the .parts suffix
        move(test_archive, self.test_cache.joinpath(f"{latest}.tar.gz.parts"))

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
            patch("umu.umu_proton._fetch_proton"),
            ThreadPoolExecutor() as thread_pool,
            patch.object(umu_proton, "unix_flock", return_value=mock_ctx),
        ):
            result = umu_proton._get_latest(
                self.env,
                compats,
                tmpdirs,
                files,
                (thread_pool, MagicMock()),
            )
            self.assertTrue(result is self.env, "Expected the same reference")
            # Verify the latest was set
            self.assertEqual(
                self.env.get("PROTONPATH"),
                self.test_compat.joinpath(latest).as_posix(),
                "Expected latest to be set",
            )
            # Verify foo files survived
            self.assertTrue(
                self.test_compat.joinpath("foo").exists(),
                "Expected foo to survive",
            )
            self.assertTrue(
                self.test_compat.joinpath("GE-Proton9-2").exists(),
                "Expected GE-Proton9-2 to survive",
            )

        latest.rmdir()
        Path(f"{latest}.sha512sum").unlink()

    def test_steamcompat_nodir(self):
        """Test _get_from_compat when Proton doesn't exist in compat dir.

        In this case, None should be returned to signal that we should
        continue with downloading the latest Proton
        """
        result = None

        result = umu_proton._get_from_compat(
            self.env, (self.test_umu_compat, self.test_compat)
        )

        self.assertFalse(result, "Expected None after calling _get_from_compat")
        self.assertFalse(self.env["PROTONPATH"], "Expected PROTONPATH to not be set")

    def test_steamcompat(self):
        """Test _get_from_compat.

        When a Proton exist in .local/share/Steam/compatibilitytools.d, use it
        when PROTONPATH is unset
        """
        result = None

        umu_util.extract_tarfile(self.test_archive, self.test_archive.parent)
        move(str(self.test_archive).removesuffix(".tar.gz"), self.test_compat)

        result = umu_proton._get_from_compat(
            self.env, (self.test_umu_compat, self.test_compat)
        )

        self.assertTrue(result is self.env, "Expected the same reference")
        self.assertEqual(
            self.env["PROTONPATH"],
            self.test_compat.joinpath(
                self.test_archive.name[: self.test_archive.name.find(".tar.gz")]
            ).as_posix(),
            "Expected PROTONPATH to be proton dir in compat",
        )

    def test_extract_tarfile_err(self):
        """Test extract_tarfile when passed a non-gzip compressed archive.

        A ReadError should be raised as we only expect .tar.gz releases
        """
        # Since 3.14, only lzma, bzip2, zstd and gzip compression is supported
        # See https://docs.python.org/3.14/library/tarfile.html#tarfile.open
        test_archive = self.test_cache.joinpath(f"{self.test_proton_dir}.tar.lz4")

        # Do not apply compression
        with tarfile.open(test_archive.as_posix(), "w") as tar:
            tar.add(
                self.test_proton_dir.as_posix(),
                arcname=self.test_proton_dir.as_posix(),
            )

        with self.assertRaisesRegex(tarfile.CompressionError, "lz4"):
            umu_util.extract_tarfile(test_archive, test_archive.parent)

        if test_archive.exists():
            test_archive.unlink()

    def test_extract_tarfile(self):
        """Test extract_tarfile.

        An error should not be raised when the Proton release is extracted to
        a temporary directory
        """
        result = None

        result = umu_util.extract_tarfile(self.test_archive, self.test_archive.parent)
        move(str(self.test_archive).removesuffix(".tar.gz"), self.test_compat)
        self.assertEqual(
            result,
            self.test_archive.parent,
            f"Expected {self.test_archive.parent}, received: {result}",
        )
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
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            args = __main__.parse_args()
            # Config
            result_env, result_dl = umu_run.check_env(self.env)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
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

        # An error should be raised if /usr/lib or /usr/lib64 is found twice
        lib_paths = set()
        for path in self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":"):
            if path not in lib_paths:
                lib_paths.add(path)
            elif path in lib_paths:
                err: str = f"Duplicate found: {path}"
                raise AssertionError(err)

        # Both of these values should be empty still after calling
        # enable_steam_game_drive
        self.assertFalse(
            self.env["STEAM_COMPAT_INSTALL_PATH"],
            "Expected STEAM_COMPAT_INSTALL_PATH to be empty",
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
        with patch("sys.argv", ["", ""]), ThreadPoolExecutor() as thread_pool:
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            args = __main__.parse_args()
            # Config
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
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
                err: str = f"Duplicate path: {path}"
                raise AssertionError(err)

        # Both of these values should be empty still after calling
        # enable_steam_game_drive
        self.assertFalse(
            self.env["STEAM_COMPAT_INSTALL_PATH"],
            "Expected STEAM_COMPAT_INSTALL_PATH to be empty",
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
        Path(self.test_file + "/proton").touch()

        # Replicate main's execution and test up until enable_steam_game_drive
        with patch("sys.argv", ["", ""]), ThreadPoolExecutor() as thread_pool:
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            args = __main__.parse_args()
            # Config
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            umu_run.set_env(self.env, args)

            # Some distributions source this variable (e.g. Ubuntu) and will
            # be added to the result of STEAM_RUNTIME_LIBRARY_PATH
            # Only test the case without it set
            if "LD_LIBRARY_PATH" in os.environ:
                os.environ.pop("LD_LIBRARY_PATH")

            # Game drive
            result_gamedrive = umu_run.enable_steam_game_drive(self.env)

        # Ubuntu sources this variable and will be added once game drive is
        # enabled. Just test the case without it
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

        # Ensure that umu sets the resolved shared library paths. The only time
        # this variable will contain links is from the LD_LIBRARY_PATH set in
        # the user's environment or client
        for path in self.env["STEAM_RUNTIME_LIBRARY_PATH"].split(":"):
            if Path(path).is_symlink():
                err = f"Symbolic link found: {path}"
                raise AssertionError(err)
            if path.endswith(
                (
                    ":",
                    "/",
                    ".",
                )
            ):  # There should be no trailing colons, slashes or periods
                err = f"Trailing character in path: {path[-1]}"
                raise AssertionError(err)

        # Both of these values should be empty still after calling
        # enable_steam_game_drive
        self.assertFalse(
            self.env["STEAM_COMPAT_INSTALL_PATH"],
            "Expected STEAM_COMPAT_INSTALL_PATH to be empty",
        )
        self.assertFalse(self.env["EXE"], "Expected EXE to be empty on empty string")

    def test_build_command_linux_exe(self):
        """Test build_command when running a Linux executable.

        UMU_NO_PROTON=1 disables Proton, running the executable directly in the
        Steam Linux Runtime.
        """
        result_args = None
        test_command = []

        # Mock the proton file
        Path(self.test_file, "proton").touch()

        # Mock the shim file
        shim_path = Path(self.test_local_share_parent, "umu-shim")
        shim_path.touch()

        with (
            patch("sys.argv", ["", self.test_exe]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            os.environ["UMU_NO_PROTON"] = "1"
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            result_args = __main__.parse_args()
            # Config
            _ = umu_run.resolve_runtime()
            # resolve_runtime's backwards compatibility is setting os.environ,
            # copy it back to self.env
            self.env["PROTONPATH"] = os.environ["PROTONPATH"]
            with (patch("umu.umu_proton.UMU_COMPAT", Path(self.test_file).resolve()),):
                self.env = umu_proton._get_umu_runtime_tool(
                    self.env, self.env["PROTONPATH"]
                )
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            umu_run.set_env(self.env, result_args)
            # Game drive
            umu_run.enable_steam_game_drive(self.env)

        os.environ |= self.env

        # Mock setting up the runtime
        with (patch.object(umu_runtime, "_install_umu", return_value=None),):
            umu_runtime.setup_umu(
                self.test_local_share,
                self.test_runtime_default,
                self.test_session_pools,
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(
                Path(self.test_user_share, "run"),
                Path(self.test_local_share, "run"),
            )
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "umu"),
                Path(self.test_local_share, "umu"),
            )
            copy(
                Path(self.test_user_share, "toolmanifest.vdf"),
                Path(self.test_local_share, "toolmanifest.vdf"),
            )
            Path(self.test_local_share, "pressure-vessel").mkdir(exist_ok=True)
            Path(self.test_local_share, "pressure-vessel", "bin").mkdir(exist_ok=True)
            copy(
                Path(
                    self.test_user_share,
                    "pressure-vessel",
                    "bin",
                    "steam-runtime-launch-client",
                ),
                Path(
                    self.test_local_share,
                    "pressure-vessel",
                    "bin",
                    "steam-runtime-launch-client",
                ),
            )

        # Build
        mock_runtime = umu_runtime.UmuRuntime(
            "sniper", "steamrt3", "1628350", self.test_local_share
        )
        with patch("umu.umu_runtime.CompatLayer.required_runtime", mock_runtime):
            test_command = umu_run.build_command(
                self.env,
                umu_runtime.CompatLayer(Path(self.env["PROTONPATH"]), shim_path),
            )
        self.assertIsInstance(
            test_command, tuple, "Expected a tuple from build_command"
        )
        self.assertEqual(
            len(test_command),
            6,
            f"Expected 5 element, received {len(test_command)}",
        )

        entry_point, verb, sep, shim, umutool, exe = [*test_command]
        self.assertEqual(
            entry_point,
            str(self.test_local_share / "umu"),
            "Expected an entry point",
        )
        self.assertEqual(verb, f"--verb={self.test_verb}", "Expected PROTON_VERB")
        self.assertEqual(sep, "--", "Expected --")
        self.assertEqual(shim, str(shim_path), "Expected path to umu")
        self.assertEqual(
            umutool, str(Path(self.test_file, "umu-sniper", "entry-point").resolve())
        )
        self.assertEqual(exe, self.env["EXE"], "Expected the EXE")

    def test_build_command_nopv_appid(self):
        """Test build_command when disabling Pressure Vessel but the tool requests a runtime.

        UMU_NO_RUNTIME=1 disables Pressure Vessel, but the tool needs
        a runtime, so use the correct runtime disregarding the env variable.

        Expects the list to contain 8 string elements.
        """
        result_args = None
        test_command = []

        # Mock the proton file
        Path(self.test_file, "proton").touch()
        # Mock a runtime toolmanifest.vdf
        Path(self.test_file, "toolmanifest.vdf").write_text(
            """
            "manifest"
            {
              "version" "2"
              "commandline" "/proton %verb%"
              "require_tool_appid" "1628350"
              "use_sessions" "1"
              "compatmanager_layer_name" "proton"
            }
            """
        )

        # Mock the shim file
        shim_path = Path(self.test_local_share_parent, "umu-shim")
        shim_path.touch()

        with (
            patch("sys.argv", ["", self.test_exe]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = str(self.test_proton_dir.resolve())
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            os.environ["UMU_NO_RUNTIME"] = "1"
            version = umu_run.resolve_runtime()
            os.environ["RUNTIMEPATH"] = version[1]
            # Args
            result_args = __main__.parse_args()
            # Config
            _, result_dl = umu_run.check_env(self.env)
            if version[1]:
                umu_run.download_proton(self.env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            umu_run.set_env(self.env, result_args)
            # Game drive
            umu_run.enable_steam_game_drive(self.env)

        # Mock setting up the runtime
        with (patch.object(umu_runtime, "_install_umu", return_value=None),):
            umu_runtime.setup_umu(
                self.test_local_share,
                self.test_runtime_default,
                self.test_session_pools,
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(
                Path(self.test_user_share, "run"),
                Path(self.test_local_share, "run"),
            )
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "umu"),
                Path(self.test_local_share, "umu"),
            )
            copy(
                Path(self.test_user_share, "toolmanifest.vdf"),
                Path(self.test_local_share, "toolmanifest.vdf"),
            )
            Path(self.test_local_share, "pressure-vessel").mkdir(exist_ok=True)
            Path(self.test_local_share, "pressure-vessel", "bin").mkdir(exist_ok=True)
            copy(
                Path(
                    self.test_user_share,
                    "pressure-vessel",
                    "bin",
                    "steam-runtime-launch-client",
                ),
                Path(
                    self.test_local_share,
                    "pressure-vessel",
                    "bin",
                    "steam-runtime-launch-client",
                ),
            )

        os.environ |= self.env

        # Build
        mock_runtime = umu_runtime.UmuRuntime(
            "sniper", "steamrt3", "1628350", self.test_local_share
        )
        with patch("umu.umu_runtime.CompatLayer.required_runtime", mock_runtime):
            test_command = umu_run.build_command(
                self.env,
                umu_runtime.CompatLayer(Path(self.env["PROTONPATH"]), shim_path),
            )
        self.assertIsInstance(
            test_command, tuple, "Expected a tuple from build_command"
        )
        self.assertEqual(
            len(test_command),
            7,
            f"Expected 7 elements, received {len(test_command)}",
        )
        _, verb, _, _, proton, _, exe = [*test_command]
        self.assertIsInstance(proton, str, "Expected proton to be str")
        self.assertEqual(
            proton,
            str(Path(self.env["PROTONPATH"], "proton")),
            "Expected PROTONPATH",
        )
        self.assertEqual(verb, "--verb=waitforexitandrun", "Expected PROTON_VERB")
        self.assertEqual(exe, self.env["EXE"], "Expected EXE")

    def test_build_command_nopv_noappid(self):
        """Test build_command when disabling Pressure Vessel and the tool doesn't request a runtime.

        UMU_NO_RUNTIME=1 disables Pressure Vessel, and the tool doesn't set
        a runtime, allow the tool to run using the host's libraries as it expects.

        Expects the list to contain 4 string elements.
        """
        result_args = None
        test_command = []

        # Mock the proton file
        Path(self.test_file, "proton").touch()
        # Mock a non-runtime toolmanifest.vdf
        Path(self.test_file, "toolmanifest.vdf").write_text(
            vdf.dumps(
                {
                    "manifest": {
                        "version": "2",
                        "commandline": "/proton %verb%",
                        "use_sessions": "1",
                        "compatmanager_layer_name": "proton",
                    }
                }
            )
        )

        # Mock the shim file
        shim_path = Path(self.test_local_share_parent, "umu-shim")
        shim_path.touch()

        with (
            patch("sys.argv", ["", self.test_exe]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = str(Path(self.test_file).resolve())
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            os.environ["UMU_NO_RUNTIME"] = "1"
            version = umu_run.resolve_runtime()
            os.environ["RUNTIMEPATH"] = version[1]
            # Args
            result_args = __main__.parse_args()
            # Config
            _, result_dl = umu_run.check_env(self.env)
            if version[1]:
                umu_run.download_proton(self.env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            umu_run.set_env(self.env, result_args)
            # Game drive
            umu_run.enable_steam_game_drive(self.env)

        # Mock setting up the runtime
        with (patch.object(umu_runtime, "_install_umu", return_value=None),):
            umu_runtime.setup_umu(
                self.test_local_share,
                self.test_runtime_default,
                self.test_session_pools,
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(
                Path(self.test_user_share, "run"),
                Path(self.test_local_share, "run"),
            )
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "umu"),
                Path(self.test_local_share, "umu"),
            )

        os.environ |= self.env

        # Build
        test_command = umu_run.build_command(
            self.env, umu_runtime.CompatLayer(Path(self.env["PROTONPATH"]), shim_path)
        )
        self.assertIsInstance(
            test_command, tuple, "Expected a tuple from build_command"
        )
        self.assertEqual(
            len(test_command),
            4,
            f"Expected 4 elements, received {len(test_command)}",
        )
        _, proton, verb, exe, *_ = [*test_command]
        self.assertIsInstance(proton, str, "Expected proton to be str")
        self.assertEqual(
            proton,
            str(Path(self.env["PROTONPATH"], "proton")),
            "Expected PROTONPATH",
        )
        self.assertEqual(verb, "waitforexitandrun", "Expected PROTON_VERB")
        self.assertEqual(exe, self.env["EXE"], "Expected EXE")

    def test_build_command_noproton(self):
        """Test build_command when $PROTONPATH/proton is not found.

        Expects a FileNotFoundError to be raised.
        """
        result_args = None

        with (
            patch("sys.argv", ["", self.test_exe]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            os.environ["UMU_NO_RUNTIME"] = "pressure-vessel"
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            result_args = __main__.parse_args()
            # Config
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            umu_run.set_env(self.env, result_args)
            # Mock setting UMU_NO_RUNTIME. This will not be set in the function
            # because the FLATPAK_PATH constant will evaluate to None
            self.env["UMU_NO_RUNTIME"] = os.environ["UMU_NO_RUNTIME"]
            # Game drive
            umu_run.enable_steam_game_drive(self.env)

        os.environ |= self.env

        # Since we didn't create the proton file, an exception should be raised
        with self.assertRaises(FileNotFoundError):
            umu_run.build_command(
                self.env, umu_runtime.CompatLayer(Path(self.test_local_share), Path())
            )

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

        # Mock the shim file
        shim_path = Path(self.test_local_share_parent, "umu-shim")
        shim_path.touch()

        with (
            patch("sys.argv", ["", self.test_exe]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = str(Path(self.test_file).resolve())
            os.environ["PROTONPATH"] = str(self.test_proton_dir.resolve())
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            result_args = __main__.parse_args()
            # Config
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            umu_run.set_env(self.env, result_args)
            # Game drive
            umu_run.enable_steam_game_drive(self.env)

        for key, val in self.env.items():
            os.environ[key] = val

        # Mock setting up the runtime
        with (patch.object(umu_runtime, "_install_umu", return_value=None),):
            umu_runtime.setup_umu(
                self.test_local_share,
                self.test_runtime_default,
                self.test_session_pools,
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(
                Path(self.test_user_share, "run"),
                Path(self.test_local_share, "run"),
            )
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "umu"),
                Path(self.test_local_share, "umu"),
            )
            copy(
                Path(self.test_user_share, "toolmanifest.vdf"),
                Path(self.test_local_share, "toolmanifest.vdf"),
            )
            Path(self.test_local_share, "pressure-vessel").mkdir(exist_ok=True)
            Path(self.test_local_share, "pressure-vessel", "bin").mkdir(exist_ok=True)
            copy(
                Path(
                    self.test_user_share,
                    "pressure-vessel",
                    "bin",
                    "steam-runtime-launch-client",
                ),
                Path(
                    self.test_local_share,
                    "pressure-vessel",
                    "bin",
                    "steam-runtime-launch-client",
                ),
            )

        # Build
        mock_runtime = umu_runtime.UmuRuntime(
            "sniper", "steamrt3", "1628350", self.test_local_share
        )
        with patch("umu.umu_runtime.CompatLayer.required_runtime", mock_runtime):
            test_command = umu_run.build_command(
                self.env,
                umu_runtime.CompatLayer(Path(self.env["PROTONPATH"]), shim_path),
            )
        self.assertIsInstance(
            test_command, tuple, "Expected a tuple from build_command"
        )
        self.assertEqual(
            len(test_command),
            7,
            f"Expected 7 elements, received {len(test_command)}",
        )
        entry_point, verb1, sep, shim, proton, verb2, exe = test_command
        # The entry point dest could change. Just check if there's a value
        self.assertTrue(entry_point, "Expected an entry point")
        self.assertIsInstance(entry_point, str, "Expected entry point to be string")
        self.assertEqual(verb1, f"--verb={self.test_verb}", "Expected a verb")
        self.assertEqual(sep, "--", "Expected --")
        self.assertIsInstance(shim, str, "Expected shim to be string")
        self.assertEqual(shim, str(shim_path), "Expected the shim file")
        self.assertIsInstance(proton, str, "Expected proton to be string")
        self.assertEqual(
            proton,
            str(Path(self.env["PROTONPATH"], "proton")),
            "Expected the proton file",
        )
        self.assertEqual(verb2, self.test_verb, "Expected a verb")
        self.assertEqual(exe, self.env["EXE"], "Expected the EXE")

    def test_set_env_opts(self):
        """Test set_env.

        Ensure no failures and verify that an option is passed to the EXE.
        """
        result = None
        test_str = "foo"

        # Replicate the command:
        # WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= umu_run ...
        with (
            patch("sys.argv", ["", self.test_exe, test_str]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = test_str
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            result = __main__.parse_args()
            # Check
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))

            # Env
            # Confirm that non-normalized paths were passed before setting
            # environment. The client will pass paths to WINEPREFIX, PROTONPATH
            # and EXE
            self.assertNotEqual(
                Path(self.test_exe),
                Path(self.test_exe).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertEqual(
                Path(os.environ["WINEPREFIX"]),
                Path(os.environ["WINEPREFIX"]).resolve(),
                "Expected path to prefix to be normalized",
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
                self.env["EXE"],
                path_exe,
                "Expected EXE to be normalized and expanded",
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
        with (
            patch("sys.argv", ["", self.test_exe]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = umu_id
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            result = __main__.parse_args()
            # Check
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
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
                hashlib.md5(
                    self.env["WINEPREFIX"].encode("utf-8")
                ).hexdigest(),  # noqa: S324
                "Expected STEAM_COMPAT_APP_ID to be the md5 hashed WINEPREFIX",
            )
            self.assertEqual(
                self.env["SteamGameId"],
                self.env["SteamAppId"],
                "Expected SteamGameId to be SteamAppId",
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
                + Path.home()
                .joinpath(".local", "share", "umu", self.test_runtime_default[1])
                .as_posix(),
                "Expected STEAM_COMPAT_TOOL_PATHS to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_MOUNTS"],
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                "Expected STEAM_COMPAT_MOUNTS to be set",
            )

    def test_set_env_exe(self):
        """Test set_env when the executable fails to be resolved.

        A FileNotFoundError should be raised and handled. Afterwards, the
        launcher will assume that the executable exists inside the WINE prefix
        or container (e.g., winecfg)
        """
        result = None
        test_str = "foo"

        # Replicate the usage:
        # WINEPREFIX= PROTONPATH= GAMEID= STORE= PROTON_VERB= umu_run ...
        with (
            patch("sys.argv", ["", test_str]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = test_str
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            result = __main__.parse_args()
            # Check
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            self.assertNotEqual(
                Path(self.test_exe),
                Path(self.test_exe).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertEqual(
                Path(os.environ["WINEPREFIX"]),
                Path(os.environ["WINEPREFIX"]).resolve(),
                "Expected path to prefix to be normalized",
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
                hashlib.md5(
                    self.env["WINEPREFIX"].encode("utf-8")
                ).hexdigest(),  # noqa: S324
                "Expected STEAM_COMPAT_APP_ID to be 0",
            )
            self.assertEqual(
                self.env["SteamGameId"],
                self.env["SteamAppId"],
                "Expected SteamGameId to be SteamAppId",
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
                + Path.home()
                .joinpath(".local", "share", "umu", self.test_runtime_default[1])
                .as_posix(),
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
        with (
            patch("sys.argv", ["", self.test_exe]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = test_str
            os.environ["STORE"] = test_str
            os.environ["PROTON_VERB"] = self.test_verb
            os.environ["UMU_RUNTIME_UPDATE"] = "0"
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            result = __main__.parse_args()
            # Check
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            self.assertNotEqual(
                Path(self.test_exe),
                Path(self.test_exe).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertEqual(
                Path(os.environ["WINEPREFIX"]),
                Path(os.environ["WINEPREFIX"]).resolve(),
                "Expected path prefix to be normalized",
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
                hashlib.md5(
                    self.env["WINEPREFIX"].encode("utf-8")
                ).hexdigest(),  # noqa: S324
                "Expected STEAM_COMPAT_APP_ID to be 0",
            )
            self.assertEqual(
                self.env["SteamGameId"],
                self.env["SteamAppId"],
                "Expected SteamGameId to be SteamAppId",
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
                + Path.home()
                .joinpath(".local", "share", "umu", self.test_runtime_default[1])
                .as_posix(),
                "Expected STEAM_COMPAT_TOOL_PATHS to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_MOUNTS"],
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                "Expected STEAM_COMPAT_MOUNTS to be set",
            )

            # Runtime
            self.assertEqual(
                os.environ.get("UMU_RUNTIME_UPDATE"),
                self.env["UMU_RUNTIME_UPDATE"],
                "Expected UMU_RUNTIME_UPDATE to be '0'",
            )

    def test_set_env_winetricks(self):
        """Test set_env when using winetricks."""
        result = None
        test_str = "foo"
        verb = "foo"
        proton_verb = "run"
        test_exe = "winetricks"

        # Mock a Proton directory that contains winetricks
        test_dir = Path("./tmp.aCAs3Q7rvz")
        if test_dir.exists():
            rmtree(test_dir)
        test_dir.joinpath("protonfixes").mkdir(parents=True)
        test_dir.joinpath("protonfixes", "winetricks").touch()

        # Replicate the usage:
        # GAMEID= umu_run winetricks ...
        with (
            patch("sys.argv", ["", "winetricks", verb]),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = test_dir.as_posix()
            os.environ["GAMEID"] = test_str
            os.environ["PROTON_VERB"] = proton_verb
            os.environ["RUNTIMEPATH"] = self.test_runtime_default[1]
            # Args
            result = __main__.parse_args()
            # Check
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)
            # Prefix
            umu_run.setup_pfx(Path(self.env["WINEPREFIX"]))
            # Env
            self.assertNotEqual(
                Path(test_exe),
                Path(test_exe).resolve(),
                "Expected path to exe to be non-normalized",
            )
            self.assertEqual(
                Path(os.environ["WINEPREFIX"]),
                Path(os.environ["WINEPREFIX"]).resolve(),
                "Expected path to prefix to be normalized",
            )
            self.assertNotEqual(
                Path(os.environ["PROTONPATH"]),
                Path(os.environ["PROTONPATH"]).resolve(),
                "Expected path to exe to be non-normalized",
            )
            result = umu_run.set_env(self.env, result[0:])
            self.assertTrue(result is self.env, "Expected the same reference")

            path_exe = (
                test_dir.joinpath("protonfixes", "winetricks")
                .expanduser()
                .resolve()
                .as_posix()
            )
            path_file = Path(self.test_file).expanduser().resolve().as_posix()

            # After calling set_env all paths should be expanded POSIX form
            self.assertEqual(
                self.env["EXE"],
                path_exe,
                "Expected EXE to be normalized and expanded",
            )
            self.assertEqual(
                self.env["PROTONPATH"],
                Path(path_exe).parent.parent.as_posix(),
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
                proton_verb,
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
                hashlib.md5(
                    self.env["WINEPREFIX"].encode("utf-8")
                ).hexdigest(),  # noqa: S324
                "Expected STEAM_COMPAT_APP_ID to be the md5 hash WINEPREFIX",
            )
            self.assertEqual(
                self.env["SteamGameId"],
                self.env["SteamAppId"],
                "Expected SteamGameId to be SteamAppId",
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
                + Path.home()
                .joinpath(".local", "share", "umu", self.test_runtime_default[1])
                .as_posix(),
                "Expected STEAM_COMPAT_TOOL_PATHS to be set",
            )
            self.assertEqual(
                self.env["STEAM_COMPAT_MOUNTS"],
                self.env["STEAM_COMPAT_TOOL_PATHS"],
                "Expected STEAM_COMPAT_MOUNTS to be set",
            )

            # Winetricks
            self.assertTrue(
                self.env["WINETRICKS_SUPER_QUIET"],
                "WINETRICKS_SUPER_QUIET is not set",
            )

        if test_dir.exists():
            rmtree(test_dir)

    def test_setup_pfx_mv(self):
        """Test setup_pfx when moving the WINEPREFIX after creating it.

        After setting up the prefix then moving it to a different path, ensure
        that the symbolic link points to that new location
        """
        result = None
        # Expects only unicode decimals and alphanumerics
        pattern = r"^/home/[\w\d]+"
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(self.test_file).cwd().joinpath(self.test_file).as_posix(),
        )
        result = umu_run.setup_pfx(Path(unexpanded_path))

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and"
            "tracked_files file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(),
            "Expected pfx to be a symlink",
        )
        self.assertTrue(
            Path(self.test_file + "/tracked_files").is_file(),
            "Expected tracked_files to be a file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(),
            "Expected pfx to be a symlink",
        )

    def test_setup_pfx_symlinks_else(self):
        """Test setup_pfx in the case both steamuser and unixuser exist.

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

        result = umu_run.setup_pfx(Path(unexpanded_path))

        self.assertIsNone(
            result,
            "Expected None when calling setup_pfx",
        )

    def test_setup_pfx_symlinks_unixuser(self):
        """Test setup_pfx for symbolic link to steamuser.

        Tests the case when the steamuser dir does not exist and user dir
        exists. In this case, create: steamuser -> user
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

        result = umu_run.setup_pfx(Path(unexpanded_path))

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

        Tests the case when only steamuser exist and the user dir does not
        exist
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

        result = umu_run.setup_pfx(Path(unexpanded_path))

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

        # Expects only unicode decimals and alphanumerics
        pattern = r"^/home/[\w\d]+"
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(self.test_file).cwd().joinpath(self.test_file).as_posix(),
        )
        result = umu_run.setup_pfx(Path(unexpanded_path))

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
            Path(self.test_file + "/pfx").is_symlink(),
            "Expected pfx to be a symlink",
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
        # Expects only unicode decimals and alphanumerics
        pattern = r"^/home/[\w\d]+"
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(self.test_file).as_posix(),
        )
        result = umu_run.setup_pfx(Path(unexpanded_path))

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and "
            "tracked_files file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(),
            "Expected pfx to be a symlink",
        )
        self.assertTrue(
            Path(self.test_file + "/tracked_files").is_file(),
            "Expected tracked_files to be a file",
        )

    def test_setup_pfx_noproton(self):
        """Test setup_pfx when configured to not use Proton."""
        self.skipTest("setup_pfx() is not called for non-proton tools")
        result = None
        os.environ["UMU_NO_PROTON"] = "1"

        result = umu_run.setup_pfx(Path(self.test_file))
        self.assertTrue(result is None, f"Expected None, received {result}")
        self.assertFalse(
            Path(self.test_file, "pfx").exists(),
            f"Expected {self.test_file}/pfx to not exist",
        )
        self.assertFalse(
            Path(self.test_file, "tracked_files").exists(),
            f"Expected {self.test_file}/tracked_files to not exist",
        )
        self.assertFalse(
            Path(self.test_file, "drive_c").exists(),
            f"Expected {self.test_file}/drive_c to not exist",
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
        result = umu_run.setup_pfx(Path(self.test_file))
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and "
            "tracked_files file",
        )
        self.assertTrue(
            Path(self.test_file + "/pfx").is_symlink(),
            "Expected pfx to be a symlink",
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

    def test_parse_args_winetricks(self):
        """Test parse_args when winetricks is the argument.

        An SystemExit should be raised when no winetricks verb is passed or if
        the value is not a winetricks verb.
        """
        with (
            patch("sys.argv", ["", "winetricks"]),
            self.assertRaises(SystemExit),
        ):
            __main__.parse_args()

    def test_parse_args_noopts(self):
        """Test parse_args with no options.

        A SystemExit should be raised in this usage: ./umu_run.py
        """
        self.skipTest("Exits cleanly")
        with self.assertRaises(SystemExit):
            __main__.parse_args()

    def test_parse_args(self):
        """Test parse_args."""
        test_opt = "foo"

        with patch("sys.argv", ["", self.test_exe, test_opt]):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["STORE"] = self.test_file

            # Args
            result = __main__.parse_args()
            self.assertIsInstance(result, tuple, "Expected a tuple")
            self.assertIsInstance(result[0], str, "Expected a string")
            self.assertIsInstance(result[1], list, "Expected a list as options")
            self.assertEqual(
                *result[1],
                test_opt,
                "Expected the test string when passed as an option",
            )

    def test_parse_args_version(self):
        """Test parse_args --version."""
        mock_val = "foo"
        opt = "version"
        with patch.object(
            __main__,
            "parse_args",
            return_value=argparse.Namespace(version=mock_val),
        ):
            result = __main__.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(
                hasattr(result, opt),
                f"Expected {result} to have attr {opt}",
            )
            self.assertEqual(
                getattr(result, opt),
                mock_val,
                f"Expected {mock_val}, received {getattr(result, opt)}",
            )

    def test_parse_args_config(self):
        """Test parse_args --config."""
        with patch.object(
            __main__,
            "parse_args",
            return_value=argparse.Namespace(config=self.test_file),
        ):
            result = __main__.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )

    def test_env_nowine_noproton(self):
        """Test check_env when configured to not use Proton.

        Expects the directory $HOME/Games/umu/$GAMEID to not be created
        when UMU_NO_PROTON=1 and GAMEID is set in the host environment.
        """
        result_env, result_dl = None, None
        # Mock $HOME
        mock_home = Path(self.test_file)

        with (
            # Mock the internal call to Path.home(). Otherwise, some of our
            # assertions may fail when running this test suite locally if
            # the user already has that dir
            patch.object(Path, "home", return_value=mock_home),
        ):
            os.environ["UMU_NO_PROTON"] = "1"
            os.environ["GAMEID"] = "foo"
            result_env, result_dl = umu_run.check_env(self.env)
            self.assertTrue(result_env is self.env)
            path = mock_home.joinpath("Games", "umu", os.environ["GAMEID"])
            # Ensure we did not create the target nor its parents up to $HOME
            self.assertFalse(path.exists(), f"Expected {path} to not exist")
            self.assertFalse(
                path.parent.exists(), f"Expected {path.parent} to not exist"
            )
            self.assertFalse(
                path.parent.parent.exists(),
                f"Expected {path.parent.parent} to not exist",
            )
            self.assertTrue(mock_home.exists(), f"Expected {mock_home} to exist")

    def test_env_wine_noproton(self):
        """Test check_env when configured to not use Proton.

        Expects the WINE prefix directory to not be created when
        UMU_NO_PROTON=1 and WINEPREFIX is set in the host environment.
        """
        result_env, result_dl = None, None

        os.environ["WINEPREFIX"] = "123"
        os.environ["UMU_NO_PROTON"] = "1"
        os.environ["GAMEID"] = "foo"
        result_env, result_dl = umu_run.check_env(self.env)
        self.assertTrue(result_env is self.env)
        self.assertFalse(
            Path(os.environ["WINEPREFIX"]).exists(),
            f"Expected directory {os.environ['WINEPREFIX']} to not exist",
        )

    def test_env_proton_nodir(self):
        """Test check_env when $PROTONPATH in the case we failed to set it.

        An FileNotFoundError should be raised when we fail to set PROTONPATH
        """
        # Mock getting the Proton
        with (
            self.assertRaises(FileNotFoundError),
            patch.object(umu_run, "get_umu_proton", return_value=self.env),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)

    def test_env_wine_empty(self):
        """Test check_env when $WINEPREFIX is empty.

        When the WINEPREFIX is empty, the current working directory of the
        user will be used as the prefix directory which should not happen.

        An ValueError should be raised
        """
        with (
            self.assertRaises(ValueError),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = ""
            os.environ["GAMEID"] = self.test_file
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)

    def test_env_gameid_empty(self):
        """Test check_env when $GAMEID is empty.

        When the GAMEID is empty in the non-config usage, no app ids will be
        set. As a result, no fixes will be applied to the current prefix

        An ValueError should be raised
        """
        with (
            self.assertRaises(ValueError),
            ThreadPoolExecutor() as thread_pool,
        ):
            os.environ["WINEPREFIX"] = ""
            os.environ["GAMEID"] = ""
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)

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

        with ThreadPoolExecutor() as thread_pool:
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)

        # After this, the WINEPREFIX and new dirs should be created
        # Update; the prefix is created in setup_pfx
        # self.assertTrue(
        #     Path(self.env["WINEPREFIX"]).exists(),
        #     "Expected WINEPREFIX to exist after check_env",
        # )
        self.assertEqual(
            self.env["WINEPREFIX"],
            os.environ["WINEPREFIX"],
            "Expected the WINEPREFIX to be set",
        )

        if Path(self.env["WINEPREFIX"]).is_dir():
            Path(self.env["WINEPREFIX"]).rmdir()

    def test_env_vars_paths(self):
        """Test check_env for unexpanded paths in $WINEPREFIX and $PROTONPATH."""
        # Expects only unicode decimals and alphanumerics
        pattern = r"^/home/[\w\d]+"
        path_to_tmp = Path(__file__).cwd().joinpath(self.test_file).as_posix()

        # Replace /home/[a-zA-Z]+ substring in path with tilda
        unexpanded_path = re.sub(
            pattern,
            "~",
            path_to_tmp,
        )

        result_env, result_dl = None, None
        os.environ["WINEPREFIX"] = unexpanded_path
        os.environ["GAMEID"] = self.test_file
        os.environ["PROTONPATH"] = unexpanded_path

        with ThreadPoolExecutor() as thread_pool:
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)

        self.assertTrue(result_env is self.env, "Expected the same reference")
        self.assertEqual(
            self.env["WINEPREFIX"],
            Path(unexpanded_path).expanduser().resolve(strict=True).as_posix(),
            "Expected WINEPREFIX to be set",
        )
        self.assertEqual(
            self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
        )
        self.assertEqual(
            self.env["PROTONPATH"],
            unexpanded_path,
            "Expected PROTONPATH to be set",
        )

    def test_env_vars(self):
        """Test check_env when setting $WINEPREFIX, $GAMEID and $PROTONPATH."""
        result_env, result_dl = None, None
        os.environ["WINEPREFIX"] = self.test_file
        os.environ["GAMEID"] = self.test_file
        os.environ["PROTONPATH"] = self.test_file

        with ThreadPoolExecutor() as thread_pool:
            result_env, result_dl = umu_run.check_env(self.env)
            umu_run.download_proton(result_env, thread_pool, download=result_dl)

        self.assertTrue(result_env is self.env, "Expected the same reference")
        self.assertEqual(
            self.env["WINEPREFIX"],
            Path(self.test_file).expanduser().resolve(strict=True).as_posix(),
            "Expected WINEPREFIX to be set",
        )
        self.assertEqual(
            self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
        )
        self.assertEqual(
            self.env["PROTONPATH"],
            self.test_file,
            "Expected PROTONPATH to be set",
        )

    def test_env_vars_proton(self):
        """Test check_env when setting only $WINEPREFIX and $GAMEID."""
        with (
            self.assertRaisesRegex(FileNotFoundError, "Proton"),
            ThreadPoolExecutor() as thread_pool,
        ):
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
                result_env, result_dl = umu_run.check_env(self.env)
                umu_run.download_proton(result_env, thread_pool, download=result_dl)
                self.assertTrue(result_env is self.env, "Expected the same reference")
                self.assertFalse(os.environ["PROTONPATH"])

    def test_env_vars_wine(self):
        """Test check_env when setting only $WINEPREFIX.

        Expects GAMEID and PROTONPATH to be set for the command line:
        """
        result_env, result_dl = None, None
        mock_gameid = "umu-default"
        mock_protonpath = str(self.test_proton_dir)

        def mock_get_umu_proton():
            os.environ["PROTONPATH"] = mock_protonpath
            return self.env

        # Mock setting the PROTONPATH
        # When running `WINEPREFIX=/some/path umu-run foo.exe` Proton is installed
        # and the GAMEID is 'umu-default'
        with patch.object(umu_run, "get_umu_proton", new_callable=mock_get_umu_proton):
            os.environ["WINEPREFIX"] = self.test_file
            result_env, result_dl = umu_run.check_env(self.env)
            self.assertTrue(result_env, self.env)
            self.assertEqual(os.environ["GAMEID"], mock_gameid)
            self.assertEqual(os.environ["GAMEID"], self.env["GAMEID"])
            self.assertEqual(os.environ["PROTONPATH"], mock_protonpath)
            self.assertEqual(os.environ["PROTONPATH"], mock_protonpath)
            self.assertTrue(
                Path(os.environ["WINEPREFIX"]).is_dir(), "Expected WINEPREFIX to exist"
            )

    def test_env_vars_none(self):
        """Tests check_env when setting no env vars.

        Expects PROTONPATH, GAMEID, and WINEPREFIX to be set
        """
        result_env, result_dl = None, None
        mock_gameid = "umu-default"
        mock_protonpath = str(self.test_proton_dir)
        mock_wineprefix = "/home/foo/Games/umu/umu-default"

        def mock_get_umu_proton():
            os.environ["PROTONPATH"] = mock_protonpath
            return self.env

        def mock_set_wineprefix():
            os.environ["WINEPREFIX"] = mock_wineprefix
            return

        # Mock setting the PROTONPATH and the WINEPREFIX creation
        # When running `umu-run foo.exe` Proton is installed WINE prefix is created
        # where the directory is 'umu-default', and the GAMEID is 'umu-default'
        with (
            patch.object(umu_run, "get_umu_proton", new_callable=mock_get_umu_proton),
            patch.object(Path, "mkdir", return_value=mock_set_wineprefix()),
        ):
            result_env, result_dl = umu_run.check_env(self.env)
            self.assertTrue(result_env, self.env)
            self.assertEqual(os.environ["GAMEID"], mock_gameid)
            self.assertEqual(os.environ["GAMEID"], self.env["GAMEID"])
            self.assertEqual(os.environ["PROTONPATH"], mock_protonpath)
            self.assertEqual(os.environ["PROTONPATH"], self.env["PROTONPATH"])
            self.assertEqual(os.environ["WINEPREFIX"], mock_wineprefix)
            self.assertEqual(os.environ["WINEPREFIX"], self.env["WINEPREFIX"])

            # Assert only PROTONPATH as WINEPREFIX involves $HOME
            self.assertTrue(
                self.test_proton_dir.is_dir(), "Expected PROTONPATH to exist"
            )


if __name__ == "__main__":
    unittest.main()
