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

    def test_parse_args(self):
    def test_set_env_toml_err(self):
        """Test set_env_toml for valid TOML
        A TOMLDecodeError should be raised for invalid values
        """
        Test parse_args with no options
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
        with self.assertRaises(SystemExit):
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
            self.assertIsInstance(result, Namespace)
            self.assertIsNone(result.config, "--config is not None")
            self.assertIsNone(result.game, "--game is not None")
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            with self.assertRaisesRegex(TOMLDecodeError, "Invalid"):
                gamelauncher.set_env_toml(env, result)

    def test_set_env_toml_nodir(self):
        """Test set_env_toml if certain key/value are not a dir

    def test_parse_args_config(self):
        An IsDirectoryError should be raised if proton or prefix are not directories
        """
        Test parse_args --config
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
            return_value=argparse.Namespace(config=test_file),
            return_value=argparse.Namespace(config=toml_path),
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(result, Namespace)
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            with self.assertRaisesRegex(KeyError, "ulwgl"):
                gamelauncher.set_env_toml(env, result)

    def test_parse_args_game(self):
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
        Test parse_args --game
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
        """
        test_file = "./tmp.WMYQiPb9A"
        with patch.object(
            gamelauncher, "parse_args", return_value=argparse.Namespace(game=test_file)
        ):
            result = gamelauncher.parse_args()
            self.assertIsInstance(result, Namespace)
            self.assertIsInstance(result, Namespace)

    def test_env_vars(self):
        """
        Test when setting WINEPREFIX, GAMEID and PROTONPATH
        """
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
