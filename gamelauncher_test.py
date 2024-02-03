import unittest
import gamelauncher
import os
import argparse
from argparse import Namespace
from unittest.mock import patch
from pathlib import Path
from tomllib import TOMLDecodeError
from shutil import rmtree


class TestGameLauncher(unittest.TestCase):
    """Test suite for gamelauncher.py.

    TODO: test for mutually exclusive options
    """

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
            "LAUNCHARGS": "",
            "SteamAppId": "",
        }
        # Test directory
        self.test_file = "./tmp.WMYQiPb9A"
        # Executable
        self.test_exe = self.test_file + "/" + "foo"
        Path(self.test_file).mkdir(exist_ok=True)
        Path(self.test_exe).touch()

    def tearDown(self):
        """Unset environment variables and delete test files after each test."""
        for key, val in self.env.items():
            if key in os.environ:
                os.environ.pop(key)

        if Path(self.test_file).exists():
            rmtree(self.test_file)

    def test_build_command_nofile(self):
        """Test build_command.

        A FileNotFoundError should be raised if $PROTONPATH/proton does not exist
        Just test the TOML case for the coverage
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        result_set_env = None
        test_command = []
        Path(toml_path).touch()
        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            result_set_env = gamelauncher.set_env_toml(self.env, result)
            self.assertIsNone(result_set_env, "Expected None after parsing TOML")
        self.env["STEAM_COMPAT_APP_ID"] = self.env["GAMEID"]
        self.env["SteamAppId"] = self.env["STEAM_COMPAT_APP_ID"]
        self.env["STEAM_COMPAT_DATA_PATH"] = self.env["WINEPREFIX"]
        self.env["STEAM_COMPAT_SHADER_PATH"] = (
            self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
        )
        for key, val in self.env.items():
            os.environ[key] = val
        with self.assertRaisesRegex(FileNotFoundError, "proton"):
            gamelauncher.build_command(self.env, test_command)

    def test_build_command_toml(self):
        """Test build_command.

        After parsing a valid TOML file, be sure we do not raise a FileNotFoundError
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        result_set_env = None
        test_command = []
        Path(self.test_file + "/proton").touch()
        Path(toml_path).touch()
        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            result_set_env = gamelauncher.set_env_toml(self.env, result)
            self.assertIsNone(result_set_env, "Expected None after parsing TOML")
        self.env["STEAM_COMPAT_APP_ID"] = self.env["GAMEID"]
        self.env["SteamAppId"] = self.env["STEAM_COMPAT_APP_ID"]
        self.env["STEAM_COMPAT_DATA_PATH"] = self.env["WINEPREFIX"]
        self.env["STEAM_COMPAT_SHADER_PATH"] = (
            self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
        )
        for key, val in self.env.items():
            os.environ[key] = val
        gamelauncher.build_command(self.env, test_command)

    def test_build_command(self):
        """Test build_command.

        After parsing valid environment variables set by the user, be sure we do not raise a FileNotFoundError
        """
        result_args = None
        result_check_env = None
        result = None
        test_command = []
        # Mock the /proton file
        Path(self.test_file + "/proton").touch()
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_file + "/foo -bar -baz"),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            result = gamelauncher.set_env(self.env, result_args)
            self.assertIsNone(
                result, "Expected None when setting environment variables"
            )
            self.assertTrue(self.env.get("EXE"), "Expected EXE to not be empty")
            self.assertTrue(
                self.env.get("LAUNCHARGS"), "Expected LAUNCHARGS to not be empty"
            )
            # Test for expected LAUNCHARGS and EXE
            self.assertEqual(
                self.env.get("LAUNCHARGS"),
                "-bar -baz",
                "Expected LAUNCHARGS to not have extra spaces",
            )
            self.assertEqual(
                self.env.get("EXE"),
                self.test_exe,
                "Expected EXE to not have extra spaces",
            )

        self.env["STEAM_COMPAT_APP_ID"] = self.env["GAMEID"]
        self.env["SteamAppId"] = self.env["STEAM_COMPAT_APP_ID"]
        self.env["STEAM_COMPAT_DATA_PATH"] = self.env["WINEPREFIX"]
        self.env["STEAM_COMPAT_SHADER_PATH"] = (
            self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
        )

        for key, val in self.env.items():
            os.environ[key] = val

        gamelauncher.build_command(self.env, test_command)

    def test_set_env_toml_opts_nofile(self):
        """Test set_env_toml for values that are not a file.

        A ValueError should be raised if an exe's arguments is a file
        """
        test_toml = "foo.toml"
        toml_path = self.test_file + "/" + test_toml
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{toml_path}"]
        exe = "{self.test_exe}"
        """
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            with self.assertRaisesRegex(ValueError, "launch arguments"):
                gamelauncher.set_env_toml(self.env, result)

    def test_set_env_toml_nofile(self):
        """Test set_env_toml for values that are not a file.

        A FileNotFoundError should be raised if the 'exe' is not a file
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        exe = "./bar"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            with self.assertRaisesRegex(FileNotFoundError, "exe"):
                gamelauncher.set_env_toml(self.env, result)

    def test_set_env_toml_empty(self):
        """Test set_env_toml for empty values not required by parse_args.

        A ValueError should be thrown if 'game_id' is empty
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = ""
        launch_args = ["{self.test_file}", "{self.test_file}"]
        exe = "{self.test_file}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            with self.assertRaisesRegex(ValueError, "game_id"):
                gamelauncher.set_env_toml(self.env, result)

    def test_set_env_toml_err(self):
        """Test set_env_toml for valid TOML.

        A TOMLDecodeError should be raised for invalid values
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = [[
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            with self.assertRaisesRegex(TOMLDecodeError, "Invalid"):
                gamelauncher.set_env_toml(self.env, result)

    def test_set_env_toml_nodir(self):
        """Test set_env_toml if certain key/value are not a dir.

        An IsDirectoryError should be raised if proton or prefix are not directories
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "foo"
        proton = "foo"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            with self.assertRaisesRegex(NotADirectoryError, "prefix"):
                gamelauncher.set_env_toml(self.env, result)

    def test_set_env_toml_tables(self):
        """Test set_env_toml for expected tables.

        A KeyError should be raised if the table 'ulwgl' is absent
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [foo]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            with self.assertRaisesRegex(KeyError, "ulwgl"):
                gamelauncher.set_env_toml(self.env, result)

    def test_set_env_toml(self):
        """Test set_env_toml."""
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        result_set_env = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            result_set_env = gamelauncher.set_env_toml(self.env, result)
            self.assertIsNone(result_set_env, "Expected None after parsing TOML")

    def test_set_env_exe_nofile(self):
        """Test set_env.

        A FileNotFoundError should be raised if a value passed to --exe is not a file
        """
        result_args = None
        result_check_env = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        # We assume everything after the first space are launch options
        # Game file names are not expected to have spaces
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(
                exe=self.test_file + "/bar" + " " + self.test_file + "/foo"
            ),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            with self.assertRaisesRegex(FileNotFoundError, "exe"):
                gamelauncher.set_env(self.env, result_args)

    def test_set_env_opts_nofile(self):
        """Test set_env.

        A ValueError should be raised if a launch option is found to be a file
        """
        result_args = None
        result_check_env = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        # We assume everything after the first space are launch options
        # Game file names are not expected to have spaces
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(
                exe=self.test_file + "/foo" + " " + self.test_file + "/foo"
            ),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            with self.assertRaisesRegex(ValueError, "launch arguments"):
                gamelauncher.set_env(self.env, result_args)

    def test_set_env_opts(self):
        """Test set_env.

        Ensure no failures and verify that $EXE and $LAUNCHARGS is not empty
        """
        result_args = None
        result_check_env = None
        result = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_file + "/foo -bar -baz"),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            result = gamelauncher.set_env(self.env, result_args)
            self.assertIsNone(
                result, "Expected None when setting environment variables"
            )
            self.assertTrue(self.env.get("EXE"), "Expected EXE to not be empty")
            self.assertTrue(
                self.env.get("LAUNCHARGS"), "Expected LAUNCHARGS to not be empty"
            )
            # Test for expected LAUNCHARGS and EXE
            self.assertEqual(
                self.env.get("LAUNCHARGS"),
                "-bar -baz",
                "Expected LAUNCHARGS to not have extra spaces",
            )
            self.assertEqual(
                self.env.get("EXE"),
                self.test_exe,
                "Expected EXE to not have extra spaces",
            )

    def test_set_env_exe(self):
        """Test set_env.

        Ensure no failures and verify that $EXE and $LAUNCHARGS is empty
        """
        result_args = None
        result_check_env = None
        result = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_exe),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            result = gamelauncher.set_env(self.env, result_args)
            self.assertIsNone(
                result, "Expected None when setting environment variables"
            )
            self.assertTrue(self.env.get("EXE"), "Expected EXE to not be empty")
            self.assertFalse(
                self.env.get("LAUNCHARGS"), "Expected LAUNCHARGS to be empty"
            )

    def test_set_env(self):
        """Test set_env.

        Ensure no failures when passing --exe and setting $WINEPREFIX and $PROTONPATH
        """
        result_args = None
        result_check_env = None
        result = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(game=self.test_file),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(result_args, Namespace)
            result_check_env = gamelauncher.check_env(self.env)
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            result = gamelauncher.set_env(self.env, result_args)
            self.assertIsNone(
                result, "Expected None when setting environment variables"
            )

    def test_setup_pfx_runtime_err(self):
        """Test _setup_pfx for RuntimeError.

        _setup_pfx expects a $WINEPREFIX as input
        Therefore one case a RuntimeError can occur is when the path to $WINEPREFIX does not exist
        """
        test_file = "./foo"
        with self.assertRaisesRegex(RuntimeError, "Error"):
            gamelauncher._setup_pfx(test_file)

            self.assertFalse(
                Path(test_file).is_dir(), "Expected WINEPREFIX to not be a directory"
            )

    def test_setup_pfx_err(self):
        """Test _setup_pfx for error.

        Ensure no error is raised when the symbolic link to $WINEPREFIX exist or if tracked_files exists
        """
        result = None
        gamelauncher._setup_pfx(self.test_file)
        result = gamelauncher._setup_pfx(self.test_file)
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix twice",
        )

    def test_setup_pfx(self):
        """Test _setup_pfx."""
        result = None
        result = gamelauncher._setup_pfx(self.test_file)
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
        """Test parse_args with no options."""
        with self.assertRaises(SystemExit):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertIsNone(result.config, "Expected --config to be None")
            self.assertIsNone(result.exe, "Expected --exe to be None")

    def test_parse_args_config(self):
        """Test parse_args --config."""
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=self.test_file),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )

    def test_parse_args_game(self):
        """Test parse_args --exe."""
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_file),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )

    def test_env_proton_dir(self):
        """Test check_env when $PROTONPATH is not a directory.

        An ValueError should occur if the value is not a directory
        """
        with self.assertRaisesRegex(ValueError, "PROTONPATH"):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["PROTONPATH"] = "./foo"
            gamelauncher.check_env(self.env)
            self.assertFalse(
                Path(os.environ["PROTONPATH"]).is_dir(),
                "Expected PROTONPATH to not be a directory",
            )

    def test_env_wine_dir(self):
        """Test check_env when $WINEPREFIX is not a directory.

        An ValueError should occur if the value is not a directory
        """
        with self.assertRaisesRegex(ValueError, "WINEPREFIX"):
            os.environ["WINEPREFIX"] = "./foo"
            os.environ["GAMEID"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            gamelauncher.check_env(self.env)
            self.assertFalse(
                Path(os.environ["WINEPREFIX"]).is_dir(),
                "Expected WINEPREFIX to not be a directory",
            )

    def test_env_vars(self):
        """Test check_env when setting $WINEPREFIX, $GAMEID and $PROTONPATH."""
        result = None
        os.environ["WINEPREFIX"] = self.test_file
        os.environ["GAMEID"] = self.test_file
        os.environ["PROTONPATH"] = self.test_file
        result = gamelauncher.check_env(self.env)
        self.assertEqual(
            self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
        )
        self.assertEqual(
            self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
        )
        self.assertEqual(
            self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
        )
        self.assertIsNone(
            result, "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set"
        )

    def test_env_vars_proton(self):
        """Test check_env when setting only $WINEPREFIX and $GAMEID."""
        with self.assertRaisesRegex(ValueError, "PROTONPATH"):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            gamelauncher.check_env(self.env)
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )

    def test_env_vars_wine(self):
        """Test check_env when setting only $WINEPREFIX."""
        with self.assertRaisesRegex(ValueError, "GAMEID"):
            os.environ["WINEPREFIX"] = self.test_file
            gamelauncher.check_env(self.env)
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )

    def test_env_vars_none(self):
        """Tests check_env when setting no env vars."""
        with self.assertRaisesRegex(ValueError, "WINEPREFIX"):
            gamelauncher.check_env(self.env)


if __name__ == "__main__":
    unittest.main()
