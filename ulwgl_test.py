import unittest
import ulwgl_run
import os
import argparse
from argparse import Namespace
from unittest.mock import patch
from pathlib import Path
from tomllib import TOMLDecodeError
from shutil import rmtree
import re
import ulwgl_plugins


class TestGameLauncher(unittest.TestCase):
    """Test suite for ulwgl_run.py.

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
        Path(self.test_file).mkdir(exist_ok=True)
        Path(self.test_exe).touch()

    def tearDown(self):
        """Unset environment variables and delete test files after each test."""
        for key, val in self.env.items():
            if key in os.environ:
                os.environ.pop(key)

        if Path(self.test_file).exists():
            rmtree(self.test_file)

    def test_game_drive_empty(self):
        """Test enable_steam_game_drive.

        Empty WINE prefixes can be created by passing an empty string to --exe
        During this process, we attempt to prepare setting up game drive and set the values for STEAM_RUNTIME_LIBRARY_PATH and STEAM_COMPAT_INSTALL_PATHS
        The resulting value of those variables should be colon delimited string with no leading colons and contain only /usr/lib or /usr/lib32
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
            # Game drive
            result_gamedrive = ulwgl_plugins.enable_steam_game_drive(self.env)

        for key, val in self.env.items():
            os.environ[key] = val

        # Game drive
        self.assertTrue(result_gamedrive is self.env, "Expected the same reference")
        self.assertTrue(
            self.env["STEAM_RUNTIME_LIBRARY_PATH"],
            "Expected two elements in STEAM_RUNTIME_LIBRARY_PATHS",
        )

        # We just expect /usr/lib and /usr/lib32
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

    def test_build_command_nofile(self):
        """Test build_command.

        A FileNotFoundError should be raised if $PROTONPATH/proton does not exist
        NOTE: Also, FileNotFoundError will be raised if the _v2-entry-point (ULWGL) is not in $HOME/.local/share/ULWGL or in cwd
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}"]
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        test_command = []
        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            # Config
            ulwgl_run.set_env_toml(self.env, result)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            ulwgl_run.set_env(self.env, result)
            # Game drive
            ulwgl_plugins.enable_steam_game_drive(self.env)

        for key, val in self.env.items():
            os.environ[key] = val

        # Build
        with self.assertRaisesRegex(FileNotFoundError, "proton"):
            ulwgl_run.build_command(self.env, test_command)

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
        test_command = []
        test_command_result = None

        Path(self.test_file + "/proton").touch()
        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            # Config
            ulwgl_run.set_env_toml(self.env, result)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            ulwgl_run.set_env(self.env, result)
            # Game drive
            ulwgl_plugins.enable_steam_game_drive(self.env)

        for key, val in self.env.items():
            os.environ[key] = val

        # Build
        test_command_result = ulwgl_run.build_command(self.env, test_command)
        self.assertTrue(
            test_command_result is test_command, "Expected the same reference"
        )

        # Verify contents of the command
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

    def test_set_env_toml_config(self):
        """Test set_env_toml when passing a configuration file.

        An FileNotFoundError should be raised when passing a TOML file that doesn't exist
        """
        test_file = "foo.toml"
        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=test_file),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            with self.assertRaisesRegex(FileNotFoundError, test_file):
                ulwgl_run.set_env_toml(self.env, result)

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
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            ulwgl_run.set_env_toml(self.env, result)

            # Check if its the TOML file we just created
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
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            with self.assertRaisesRegex(FileNotFoundError, "exe"):
                ulwgl_run.set_env_toml(self.env, result)

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
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            # Env
            with self.assertRaisesRegex(TOMLDecodeError, "Invalid"):
                ulwgl_run.set_env_toml(self.env, result)

    def test_set_env_toml_nodir(self):
        """Test set_env_toml if certain key/value are not a dir.

        An IsDirectoryError should be raised if the following keys are not dir: proton, prefix
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
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            with self.assertRaisesRegex(NotADirectoryError, "proton"):
                ulwgl_run.set_env_toml(self.env, result)

    def test_set_env_toml_tables(self):
        """Test set_env_toml for expected tables.

        A ValueError should be raised if the following tables are absent: ulwgl
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
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            with self.assertRaisesRegex(ValueError, "ulwgl"):
                ulwgl_run.set_env_toml(self.env, result)

    def test_set_env_toml_paths(self):
        """Test set_env_toml when specifying unexpanded file path values in the config file.

        Example: ~/Games/foo.exe
        An error should not be raised when passing unexpanded paths to the config file as well as the prefix, proton and exe keys
        """
        test_toml = "foo.toml"
        pattern = r"^/home/[a-zA-Z]+"

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        path_to_tmp = Path(
            Path(__file__).cwd().as_posix() + "/" + self.test_file
        ).as_posix()
        path_to_exe = Path(
            Path(__file__).cwd().as_posix() + "/" + self.test_exe
        ).as_posix()

        # Replace /home/[a-zA-Z]+ substring in path with tilda
        unexpanded_path = re.sub(
            pattern,
            "~",
            path_to_tmp,
        )
        unexpanded_exe = re.sub(
            pattern,
            "~",
            path_to_exe,
        )
        toml_str = f"""
        [ulwgl]
        prefix = "{unexpanded_path}"
        proton = "{unexpanded_path}"
        game_id = "{unexpanded_path}"
        exe = "{unexpanded_exe}"
        """
        # Path to TOML in unexpanded form
        toml_path = unexpanded_path + "/" + test_toml
        result = None
        result_set_env = None

        Path(toml_path).expanduser().touch()

        with Path(toml_path).expanduser().open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            result_set_env = ulwgl_run.set_env_toml(self.env, result)
            self.assertTrue(result_set_env is self.env, "Expected the same reference")

            # Check that the paths are still in the unexpanded form after setting the env
            # In main, we only expand them after this function exits to prepare for building the command
            self.assertEqual(
                self.env["EXE"], unexpanded_exe, "Expected path not to be expanded"
            )
            self.assertEqual(
                self.env["PROTONPATH"],
                unexpanded_path,
                "Expected path not to be expanded",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                unexpanded_path,
                "Expected path not to be expanded",
            )
            self.assertEqual(
                self.env["GAMEID"], unexpanded_path, "Expectd path not to be expanded"
            )

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
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            result_set_env = ulwgl_run.set_env_toml(self.env, result)
            self.assertTrue(result_set_env is self.env, "Expected the same reference")
            self.assertTrue(self.env["EXE"], "Expected EXE to be set")
            self.assertEqual(
                self.env["EXE"],
                self.test_exe + " " + " ".join([self.test_file, self.test_file]),
                "Expectd GAMEID to be set",
            )
            self.assertEqual(
                self.env["PROTONPATH"],
                self.test_file,
                "Expected PROTONPATH to be set",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                self.test_file,
                "Expected WINEPREFIX to be set",
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expectd GAMEID to be set"
            )

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
        pattern = r"^/home/[a-zA-Z]+"
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(
                Path(self.test_file).cwd().as_posix() + "/" + self.test_file
            ).as_posix(),
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
        pattern = r"^/home/[a-zA-Z]+"
        unexpanded_path = re.sub(
            pattern,
            "~",
            Path(Path(self.test_file).as_posix()).as_posix(),
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

    def test_env_proton_dir(self):
        """Test check_env when $PROTONPATH is not a directory.

        An ValueError should occur if the value is not a directory
        """
        with self.assertRaisesRegex(ValueError, "PROTONPATH"):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            os.environ["PROTONPATH"] = "./foo"
            ulwgl_run.check_env(self.env)
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
        ulwgl_run.check_env(self.env)
        self.assertEqual(
            Path(os.environ["WINEPREFIX"]).is_dir(),
            True,
            "Expected WINEPREFIX to be created if not already exist",
        )
        if Path(os.environ["WINEPREFIX"]).is_dir():
            rmtree(os.environ["WINEPREFIX"])

    def test_env_vars_paths(self):
        """Test check_env when setting unexpanded paths for $WINEPREFIX and $PROTONPATH."""
        pattern = r"^/home/[a-zA-Z]+"
        path_to_tmp = Path(
            Path(__file__).cwd().as_posix() + "/" + self.test_file
        ).as_posix()

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
        with self.assertRaisesRegex(ValueError, "PROTONPATH"):
            os.environ["WINEPREFIX"] = self.test_file
            os.environ["GAMEID"] = self.test_file
            ulwgl_run.check_env(self.env)

    def test_env_vars_wine(self):
        """Test check_env when setting only $WINEPREFIX."""
        with self.assertRaisesRegex(ValueError, "GAMEID"):
            os.environ["WINEPREFIX"] = self.test_file
            ulwgl_run.check_env(self.env)

    def test_env_vars_none(self):
        """Tests check_env when setting no env vars."""
        with self.assertRaisesRegex(ValueError, "WINEPREFIX"):
            ulwgl_run.check_env(self.env)


if __name__ == "__main__":
    unittest.main()
