import unittest
import gamelauncher
import os
import argparse
from argparse import Namespace
from unittest.mock import patch
from pathlib import Path
from tomllib import TOMLDecodeError


class TestGameLauncher(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        """
        Unset environment variables
        """
        test_file = "./tmp.WMYQiPb9A"
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        for key, val in env.items():
            if key in os.environ:
                os.environ.pop(key)

        if (
            os.path.exists(test_file)
            and os.path.isfile(test_file + "/tracked_files")
            and os.path.islink(test_file + "/pfx")
        ):
            os.remove(test_file + "/tracked_files")
            os.unlink(test_file + "/pfx")
            if os.path.isfile(test_file + "/foo.toml"):
                os.remove(test_file + "/foo.toml")

    def test_set_env_toml_err(self):
        """Test set_env_toml for valid TOML

        A TOMLDecodeError should be raised for invalid values
        """
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        test_file = "./tmp.WMYQiPb9A"
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = [[
        proton = "{test_file}"
        game_id = "{test_file}"
        launch_opts = ["{test_file}", "{test_file}"]
        """
        toml_path = test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with open(toml_path, "w") as file:
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
                gamelauncher.set_env_toml(env, result)

    def test_set_env_toml_nodir(self):
        """Test set_env_toml if certain key/value are not a dir

        An IsDirectoryError should be raised if proton or prefix are not directories
        """
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        test_file = "./tmp.WMYQiPb9A"
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "foo"
        proton = "foo"
        game_id = "{test_file}"
        launch_opts = ["{test_file}", "{test_file}"]
        """
        toml_path = test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with open(toml_path, "w") as file:
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
                gamelauncher.set_env_toml(env, result)

    def test_set_env_toml_tables(self):
        """Test set_env_toml for expected tables

        A KeyError should be raised if the table 'ulwgl' is absent
        """
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        test_file = "./tmp.WMYQiPb9A"
        test_toml = "foo.toml"
        toml_str = f"""
        [foo]
        prefix = "{test_file}"
        proton = "{test_file}"
        game_id = "{test_file}"
        launch_opts = ["{test_file}", "{test_file}"]
        """
        toml_path = test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with open(toml_path, "w") as file:
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
                gamelauncher.set_env_toml(env, result)

    def test_set_env_toml(self):
        """Test set_env_toml"""
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        test_file = "./tmp.WMYQiPb9A"
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{test_file}"
        proton = "{test_file}"
        game_id = "{test_file}"
        launch_opts = ["{test_file}", "{test_file}"]
        """
        toml_path = test_file + "/" + test_toml
        result = None
        result_set_env = None

        Path(toml_path).touch()

        with open(toml_path, "w") as file:
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
            result_set_env = gamelauncher.set_env_toml(env, result)
            self.assertIsNone(result_set_env, "Expected None after parsing TOML")

    def test_set_env_opts(self):
        """Test set_env

        Ensure no failures and verify that EXE and LAUNCHARGS is not empty
        """
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        test_file = "./tmp.WMYQiPb9A"
        result_args = None
        result_check_env = None
        result = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --game=...
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(game="foo -bar -baz"),
        ):
            os.environ["WINEPREFIX"] = test_file
            os.environ["PROTONPATH"] = test_file
            os.environ["GAMEID"] = test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(env)
            self.assertEqual(
                env["WINEPREFIX"], test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(env["GAMEID"], test_file, "Expected GAMEID to be set")
            self.assertEqual(
                env["PROTONPATH"], test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            result = gamelauncher.set_env(env, result_args)
            self.assertIsNone(
                result, "Expected None when setting environment variables"
            )
            self.assertTrue(env.get("EXE"), "Expected EXE to not be empty")
            self.assertTrue(
                env.get("LAUNCHARGS"), "Expected LAUNCHARGS to not be empty"
            )
            # Test for expected LAUNCHARGS and EXE
            self.assertEqual(
                env.get("LAUNCHARGS"),
                "-bar -baz",
                "Expected LAUNCHARGS to not have extra spaces",
            )
            self.assertEqual(
                env.get("EXE"), "foo", "Expected EXE to not have extra spaces"
            )

    def test_set_env_exe(self):
        """Test set_env

        Ensure no failures and verify that EXE and LAUNCHARGS is empty
        """
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        test_file = "./tmp.WMYQiPb9A"
        result_args = None
        result_check_env = None
        result = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --game=...
        with patch.object(
            gamelauncher, "parse_args", return_value=argparse.Namespace(game=test_file)
        ):
            os.environ["WINEPREFIX"] = test_file
            os.environ["PROTONPATH"] = test_file
            os.environ["GAMEID"] = test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(
                result_args, Namespace, "parse_args did not return a Namespace"
            )
            result_check_env = gamelauncher.check_env(env)
            self.assertEqual(
                env["WINEPREFIX"], test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(env["GAMEID"], test_file, "Expected GAMEID to be set")
            self.assertEqual(
                env["PROTONPATH"], test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            result = gamelauncher.set_env(env, result_args)
            self.assertIsNone(
                result, "Expected None when setting environment variables"
            )
            self.assertTrue(env.get("EXE"), "Expected EXE to not be empty")
            self.assertFalse(env.get("LAUNCHARGS"), "Expected LAUNCHARGS to be empty")

    def test_set_env(self):
        """Test set_env

        Ensure no failures when passing --game and setting $WINEPREFIX and $PROTONPATH
        """
        Test when setting WINEPREFIX, GAMEID and PROTONPATH
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        test_file = "./tmp.WMYQiPb9A"
        result_args = None
        result_check_env = None
        result = None
        # Replicate the usage WINEPREFIX= PROTONPATH= GAMEID= gamelauncher --game=...
        with patch.object(
            gamelauncher, "parse_args", return_value=argparse.Namespace(game=test_file)
        ):
            os.environ["WINEPREFIX"] = test_file
            os.environ["PROTONPATH"] = test_file
            os.environ["GAMEID"] = test_file
            result_args = gamelauncher.parse_args()
            self.assertIsInstance(result_args, Namespace)
            result_check_env = gamelauncher.check_env(env)
            self.assertEqual(
                env["WINEPREFIX"], test_file, "Expected WINEPREFIX to be set"
            )
            self.assertEqual(env["GAMEID"], test_file, "Expected GAMEID to be set")
            self.assertEqual(
                env["PROTONPATH"], test_file, "Expected PROTONPATH to be set"
            )
            self.assertIsNone(
                result_check_env,
                "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set",
            )
            result = gamelauncher.set_env(env, result_args)
            self.assertIsNone(
                result, "Expected None when setting environment variables"
            )

    def test_setup_pfx_runtime_err(self):
        """Test _setup_pfx for RuntimeError

        _setup_pfx expects a $WINEPREFIX as input
        Therefore one case a RuntimeError can occur is when the path to $WINEPREFIX does not exist
        """
        test_file = "./foo"
        with self.assertRaisesRegex(RuntimeError, "Error"):
            gamelauncher._setup_pfx(test_file)
            self.assertFalse(
                os.path.isdir(test_file), "Expected WINEPREFIX to not be a directory"
            )

    def test_setup_pfx_err(self):
        """Test _setup_pfx for error

        Ensure no error is raised when the symbolic link to $WINEPREFIX exist
        """
        test_file = "./tmp.WMYQiPb9A"
        result = None
        gamelauncher._setup_pfx(test_file)
        result = gamelauncher._setup_pfx(test_file)
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix twice",
        )

    def test_setup_pfx(self):
        """Test _setup_pfx"""
        test_file = "./tmp.WMYQiPb9A"
        result = None
        result = gamelauncher._setup_pfx(test_file)
        self.assertIsNone(
            result,
            "Expected None when creating symbolic link to WINE prefix and tracked_files file",
        )
        self.assertTrue(
            os.path.islink(test_file + "/pfx"), "Expected pfx to be a symlink"
        )
        self.assertTrue(
            os.path.isfile(test_file + "/tracked_files"),
            "Expected tracked_files to be a file",
        )

    def test_parse_args(self):
        """Test parse_args with no options"""
        with self.assertRaises(SystemExit):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertIsNone(result.config, "Expected --config to be None")
            self.assertIsNone(result.game, "Expected --game to be None")

    def test_parse_args_config(self):
        """Test parse_args --config"""
        test_file = "./tmp.WMYQiPb9A"
        with patch.object(
            gamelauncher,
            "parse_args",
            return_value=argparse.Namespace(config=test_file),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )

    def test_parse_args_game(self):
        """Test parse_args --game"""
        test_file = "./tmp.WMYQiPb9A"
        with patch.object(
            gamelauncher, "parse_args", return_value=argparse.Namespace(game=test_file)
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )

    def test_env_vars(self):
        """Test check_env when setting WINEPREFIX, GAMEID and PROTONPATH"""
        test_file = "./tmp.WMYQiPb9A"
        result = None
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        os.environ["WINEPREFIX"] = test_file
        os.environ["GAMEID"] = test_file
        os.environ["PROTONPATH"] = test_file
        result = gamelauncher.check_env(env)
        self.assertEqual(env["WINEPREFIX"], test_file)
        self.assertEqual(env["GAMEID"], test_file)
        self.assertEqual(env["PROTONPATH"], test_file)
        self.assertIsNone(
            result, "Expected None when WINEPREFIX, GAMEID and PROTONPATH are set"
        )

    def test_env_vars_proton(self):
        """
        Test when setting only WINEPREFIX and GAMEID
        """
        test_file = "./tmp.WMYQiPb9A"
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        with self.assertRaisesRegex(ValueError, "PROTONPATH"):
            os.environ["WINEPREFIX"] = test_file
            os.environ["GAMEID"] = test_file
            gamelauncher.check_env(env)
            self.assertEqual(env["WINEPREFIX"], test_file)
            self.assertEqual(env["GAMEID"], test_file)

    def test_env_vars_wine(self):
        """
        Test when setting only WINEPREFIX
        """
        test_file = "./tmp.WMYQiPb9A"
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        with self.assertRaisesRegex(ValueError, "GAMEID"):
            os.environ["WINEPREFIX"] = test_file
            gamelauncher.check_env(env)
            self.assertEqual(env["WINEPREFIX"], test_file)

    def test_env_vars_none(self):
        """
        Tests when setting no env vars
        """
        env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "CRASH_REPORT": "/tmp/ULWGL_crashreports",
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
        with self.assertRaisesRegex(KeyError, "WINEPREFIX"):
            gamelauncher.check_env(env)


if __name__ == "__main__":
    unittest.main()
