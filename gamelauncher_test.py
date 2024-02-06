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
            "SteamAppId": "",
            "SteamGameId": "",
            "STEAM_RUNTIME_LIBRARY_PATH": "",
        }
        self.test_opts = "-foo -bar"
        # Proton verb
        # Used when testing build_command
        self.test_verb = "waitforexitandrun"
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

    def test_build_command_verb(self):
        """Test build_command.

        An error should not be raised if we pass a Proton verb we don't expect
        By default, we use "waitforexitandrun" for a verb we don't expect
        Currently we only expect:
            "waitforexitandrun"
            "run"
            "runinprefix"
            "destroyprefix"
            "getcompatpath"
            "getnativepath"
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
        test_verb = "foo"
        Path(self.test_file + "/proton").touch()
        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path, verb=test_verb),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Check if a verb was passed
            self.assertTrue(vars(result).get("verb"), "Expected a value for --verb")
            result_set_env = gamelauncher.set_env_toml(self.env, result)
            self.assertIsInstance(
                result_set_env, dict, "Expected a Dictionary from set_env_toml"
            )
            # Check for changes after calling
            self.assertEqual(
                result_set_env["EXE"],
                self.test_exe + " " + self.test_file + " " + self.test_file,
            )
            self.assertEqual(result_set_env["WINEPREFIX"], self.test_file)
            self.assertEqual(result_set_env["PROTONPATH"], self.test_file)
            self.assertEqual(result_set_env["GAMEID"], self.test_file)

        self.env["STEAM_COMPAT_APP_ID"] = self.env["GAMEID"]
        self.env["SteamAppId"] = self.env["STEAM_COMPAT_APP_ID"]
        self.env["SteamGameId"] = self.env["SteamAppId"]
        self.env["STEAM_COMPAT_DATA_PATH"] = self.env["WINEPREFIX"]
        self.env["STEAM_COMPAT_SHADER_PATH"] = (
            self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
        )
        self.env["STEAM_COMPAT_INSTALL_PATH"] = Path(self.env["EXE"]).parent.as_posix()
        self.env["STEAM_COMPAT_TOOL_PATHS"] = Path(
            self.env["PROTONPATH"]
        ).parent.as_posix()
        self.env["STEAM_COMPAT_MOUNTS"] = self.env["STEAM_COMPAT_TOOL_PATHS"]

        # Create an empty Proton prefix when asked
        if not getattr(result, "exe", None) and not getattr(result, "config", None):
            self.env["EXE"] = ""
            self.env["STEAM_COMPAT_INSTALL_PATH"] = ""
            self.verb = "waitforexitandrun"

        for key, val in self.env.items():
            os.environ[key] = val
        test_command = gamelauncher.build_command(self.env, test_command, test_verb)
        # The verb should be 2nd in the array
        self.assertIsInstance(test_command, list, "Expected a List from build_command")
        self.assertTrue(test_command[2], self.test_verb)

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
            self.assertIsInstance(
                result_set_env, dict, "Expected a Dictionary from set_env_toml"
            )
            # Check for changes after calling
            self.assertEqual(
                result_set_env["EXE"],
                self.test_exe + " " + self.test_file + " " + self.test_file,
            )
            self.assertEqual(result_set_env["WINEPREFIX"], self.test_file)
            self.assertEqual(result_set_env["PROTONPATH"], self.test_file)
            self.assertEqual(result_set_env["GAMEID"], self.test_file)

        self.env["STEAM_COMPAT_APP_ID"] = self.env["GAMEID"]
        self.env["SteamAppId"] = self.env["STEAM_COMPAT_APP_ID"]
        self.env["SteamGameId"] = self.env["SteamAppId"]
        self.env["STEAM_COMPAT_DATA_PATH"] = self.env["WINEPREFIX"]
        self.env["STEAM_COMPAT_SHADER_PATH"] = (
            self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
        )
        self.env["STEAM_COMPAT_INSTALL_PATH"] = Path(self.env["EXE"]).parent.as_posix()
        self.env["STEAM_COMPAT_TOOL_PATHS"] = Path(
            self.env["PROTONPATH"]
        ).parent.as_posix()
        self.env["STEAM_COMPAT_MOUNTS"] = self.env["STEAM_COMPAT_TOOL_PATHS"]

        # Create an empty Proton prefix when asked
        if not getattr(result, "exe", None) and not getattr(result, "config", None):
            self.env["EXE"] = ""
            self.env["STEAM_COMPAT_INSTALL_PATH"] = ""
            self.verb = "waitforexitandrun"

        for key, val in self.env.items():
            os.environ[key] = val
        with self.assertRaisesRegex(FileNotFoundError, "proton"):
            gamelauncher.build_command(self.env, test_command, self.test_verb)

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
            self.assertIsInstance(
                result_set_env, dict, "Expected a Dictionary from set_env_toml"
            )
            # Check for changes after calling
            self.assertEqual(
                result_set_env["EXE"],
                self.test_exe + " " + self.test_file + " " + self.test_file,
            )
            self.assertEqual(result_set_env["WINEPREFIX"], self.test_file)
            self.assertEqual(result_set_env["PROTONPATH"], self.test_file)
            self.assertEqual(result_set_env["GAMEID"], self.test_file)

        self.env["STEAM_COMPAT_APP_ID"] = self.env["GAMEID"]
        self.env["SteamAppId"] = self.env["STEAM_COMPAT_APP_ID"]
        self.env["SteamGameId"] = self.env["SteamAppId"]
        self.env["STEAM_COMPAT_DATA_PATH"] = self.env["WINEPREFIX"]
        self.env["STEAM_COMPAT_SHADER_PATH"] = (
            self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
        )
        self.env["STEAM_COMPAT_INSTALL_PATH"] = Path(self.env["EXE"]).parent.as_posix()
        self.env["STEAM_COMPAT_TOOL_PATHS"] = Path(
            self.env["PROTONPATH"]
        ).parent.as_posix()
        self.env["STEAM_COMPAT_MOUNTS"] = self.env["STEAM_COMPAT_TOOL_PATHS"]

        # Create an empty Proton prefix when asked
        if not getattr(result, "exe", None) and not getattr(result, "config", None):
            self.env["EXE"] = ""
            self.env["STEAM_COMPAT_INSTALL_PATH"] = ""
            self.verb = "waitforexitandrun"

        for key, val in self.env.items():
            os.environ[key] = val
        test_command = gamelauncher.build_command(
            self.env, test_command, self.test_verb
        )
        self.assertIsInstance(test_command, list, "Expected a List from build_command")
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

    def test_build_command(self):
        """Test build_command.

        After parsing valid environment variables set by the user, be sure we do not raise a FileNotFoundError
        """
        result_args = None
        result_check_env = None
        test_command = []

        # Mock the /proton file
        Path(self.test_file + "/proton").touch()

        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_exe, options=self.test_opts),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertIsInstance(
                result_check_env, dict, "Expected a Dictionary from set_env_toml"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            result_set_env = gamelauncher.set_env(self.env, result_args)

            # Check for changes after calling
            self.assertEqual(result_set_env["WINEPREFIX"], self.test_file)
            self.assertEqual(result_set_env["PROTONPATH"], self.test_file)
            self.assertEqual(result_set_env["GAMEID"], self.test_file)
            # Test for expected EXE with options
            self.assertEqual(
                self.env.get("EXE"),
                "{} {}".format(self.test_exe, self.test_opts),
                "Expected the concat EXE and game options to not have trailing spaces",
            )

        self.env["STEAM_COMPAT_APP_ID"] = self.env["GAMEID"]
        self.env["SteamAppId"] = self.env["STEAM_COMPAT_APP_ID"]
        self.env["SteamGameId"] = self.env["SteamAppId"]
        self.env["STEAM_COMPAT_DATA_PATH"] = self.env["WINEPREFIX"]
        self.env["STEAM_COMPAT_SHADER_PATH"] = (
            self.env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
        )
        self.env["STEAM_COMPAT_INSTALL_PATH"] = Path(self.env["EXE"]).parent.as_posix()
        self.env["STEAM_COMPAT_TOOL_PATHS"] = Path(
            self.env["PROTONPATH"]
        ).parent.as_posix()
        self.env["STEAM_COMPAT_MOUNTS"] = self.env["STEAM_COMPAT_TOOL_PATHS"]

        # Create an empty Proton prefix when asked
        if not getattr(result_args, "exe", None) and not getattr(
            result_args, "config", None
        ):
            self.env["EXE"] = ""
            self.env["STEAM_COMPAT_INSTALL_PATH"] = ""
            self.verb = "waitforexitandrun"

        for key, val in self.env.items():
            os.environ[key] = val

        test_command = gamelauncher.build_command(
            self.env, test_command, self.test_verb
        )
        self.assertIsInstance(test_command, list, "Expected a List from build_command")
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

    def test_set_env_toml_config(self):
        """Test set_env_toml when passing a configuration file.

        An FileNotFoundError should be raised when passing a TOML file that doesn't exist
        """
        test_file = "foo.toml"
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=test_file),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            with self.assertRaisesRegex(FileNotFoundError, test_file):
                gamelauncher.set_env_toml(self.env, result)

    def test_set_env_toml_opts_nofile(self):
        """Test set_env_toml for options that are a file.

        An error should not be raised if a launch argument is a file
        We allow this behavior to give users flexibility at the cost of security
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
            gamelauncher.set_env_toml(self.env, result)
            # Check if the TOML file we just created
            self.assertTrue(
                Path(self.env["EXE"].split(" ")[1]).is_file(),
                "Expected a file to be appended to the executable",
            )

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
            self.assertIsInstance(
                result_set_env, dict, "Expected a Dictionary from set_env_toml"
            )

    def test_set_env_exe_nofile(self):
        """Test set_env when setting no options via --options and appending options to --exe.

        gamelauncher.py --exe "foo -bar"
        Options can be appended at the end of the exe if wrapping the value in quotes
        No error should be raised if the --exe passed by the user doesn't exist
        We trust the user that its legit and only validate the EXE in the TOML case
        """
        result_args = None
        result_check_env = None
        result_set_env = None

        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_exe + " foo"),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertIsInstance(
                result_check_env, dict, "Expected a Dictionary from check_env"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            result_set_env = gamelauncher.set_env(self.env, result_args)
            self.assertIsInstance(
                result_set_env, dict, "Expected a Dictionary from set_env"
            )
            self.assertEqual(
                self.env["EXE"],
                self.test_exe + " foo",
                "Expected EXE to be set after passing garbage",
            )
            self.assertTrue(Path(self.test_exe).exists(), "Expected the EXE to exist")
            self.assertFalse(
                Path(self.test_exe + " foo").exists(),
                "Expected the concat of EXE and options to not exist",
            )

    def test_set_env_opts_nofile(self):
        """Test set_env when an exe's options is a file.

        We allow options that may or may not be legit
        No error should be raised in this case and we just check if options are a file
        """
        result_args = None
        result_check_env = None
        result_set_env = None

        # File that will be passed as an option to the exe
        test_opts_file = "baz"
        Path(test_opts_file).touch()

        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_exe, options=test_opts_file),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertIsInstance(
                result_check_env, dict, "Expected a Dictionary from check_env"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            result_set_env = gamelauncher.set_env(self.env, result_args)
            self.assertIsInstance(
                result_set_env, dict, "Expected a Dictionary from set_env"
            )
            self.assertEqual(
                self.env["EXE"],
                self.test_exe + " " + test_opts_file,
                "Expected EXE to be set after appending a file as an option",
            )
            # The concat of exe and options shouldn't be a file
            self.assertFalse(
                Path(self.env["EXE"]).is_file(),
                "Expected EXE to not be a file when passing options",
            )
            # However each part is a file
            self.assertTrue(
                Path(test_opts_file).is_file(),
                "Expected a file for this test to be used as an option",
            )
            self.assertTrue(
                Path(self.test_exe).is_file(),
                "Expected a file for this test to be used as an option",
            )
            Path(test_opts_file).unlink()

    def test_set_env_opts(self):
        """Test set_env.

        Ensure no failures and verify that $EXE is set with options passed
        """
        result_args = None
        result_check_env = None
        result = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --exe=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_exe, options=self.test_opts),
        ):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["PROTONPATH"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(self.env)
            self.assertIsInstance(
                result_check_env, dict, "Expected a Dictionary from check_env"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            result = gamelauncher.set_env(self.env, result_args)
            self.assertIsInstance(result, dict, "Expected a Dictionary from set_env")
            self.assertTrue(self.env.get("EXE"), "Expected EXE to not be empty")
            self.assertEqual(
                self.env.get("EXE"),
                self.test_exe + " " + self.test_opts,
                "Expected EXE to not have trailing spaces",
            )

    def test_set_env_exe(self):
        """Test set_env.

        Ensure no failures and verify that $EXE
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
            self.assertIsInstance(
                result_check_env, dict, "Expected a Dictionary from check_env"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            result = gamelauncher.set_env(self.env, result_args)
            self.assertIsInstance(result, dict, "Expected a Dictionary from set_env")
            self.assertTrue(self.env.get("EXE"), "Expected EXE to not be empty")

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
            self.assertIsInstance(
                result_check_env, dict, "Expected a Dictionary from check_env"
            )
            self.assertEqual(
                self.env["WINEPREFIX"], self.test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )
            self.assertEqual(
                self.env["PROTONPATH"], self.test_file, "Expected PROTONPATH to be set"
            )
            result = gamelauncher.set_env(self.env, result_args)
            self.assertIsInstance(result, dict, "Expected a Dictionary from set_env")

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
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix twice",
        )

    def test_parse_args_verb(self):
        """Test parse_args --verb."""
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_exe, verb=self.test_verb),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertEqual(
                result.verb,
                self.test_verb,
                "Expected the same value when setting --verb",
            )

    def test_parse_args_options(self):
        """Test parse_args --options."""
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(exe=self.test_exe, options=self.test_opts),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertEqual(
                result.options,
                self.test_opts,
                "Expected the same value when setting --options",
            )

    def test_parse_args(self):
        """Test parse_args with no options.

        There's a requirement to create an empty prefix
        A SystemExit should be raised in this case:
        ./gamelauncher.py
        """
        with self.assertRaises(SystemExit):
            gamelauncher.parse_args()

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

        An error should not be raised if a WINEPREFIX is set but the path has not been created.
        """
        os.environ["WINEPREFIX"] = "./foo"
        os.environ["GAMEID"] = self.test_file
        os.environ["PROTONPATH"] = self.test_file
        gamelauncher.check_env(self.env)
        self.assertEqual(
            Path(os.environ["WINEPREFIX"]).is_dir(),
            True,
            "Expected WINEPREFIX to be created if not already exist",
        )
        if Path(os.environ["WINEPREFIX"]).is_dir():
            rmtree(os.environ["WINEPREFIX"])

    def test_env_vars(self):
        """Test check_env when setting $WINEPREFIX, $GAMEID and $PROTONPATH."""
        result = None
        os.environ["WINEPREFIX"] = self.test_file
        os.environ["GAMEID"] = self.test_file
        os.environ["PROTONPATH"] = self.test_file
        result = gamelauncher.check_env(self.env)
        self.assertIsInstance(result, dict, "Expected a Dictionary from set_env_toml")
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