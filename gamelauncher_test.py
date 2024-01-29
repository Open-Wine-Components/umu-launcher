import unittest
import gamelauncher
import os
import argparse
from argparse import Namespace
from unittest.mock import patch


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
        """
        Test parse_args with no options
        """
        test_file = "./tmp.WMYQiPb9A"
        with self.assertRaises(SystemExit):
            result = gamelauncher.parse_args()
            self.assertIsInstance(result, Namespace)
            self.assertIsNone(result.config, "--config is not None")
            self.assertIsNone(result.game, "--game is not None")

    def test_parse_args_config(self):
        """
        Test parse_args --config
        """
        test_file = "./tmp.WMYQiPb9A"
        with patch.object(gamelauncher, 'parse_args', return_value=argparse.Namespace(config=test_file)):
            result = gamelauncher.parse_args()
            self.assertIsInstance(result, Namespace)

    def test_parse_args_game(self):
        """
        Test parse_args --game
        """
        test_file = "./tmp.WMYQiPb9A"
        with patch.object(gamelauncher, 'parse_args', return_value=argparse.Namespace(game=test_file)):
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
