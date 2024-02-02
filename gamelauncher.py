#!/usr/bin/env python3

import os
import argparse
from argparse import ArgumentParser, _ArgumentGroup, Namespace
import sys
from pathlib import Path
import tomllib
from tomllib import TOMLDecodeError
from typing import Dict, Any, Union
# TODO: add checks for EXE is a file and LAUNCHARGS is a string


def parse_args() -> Namespace:
    parser: ArgumentParser = argparse.ArgumentParser(
        description="Unified Linux Wine Game Launcher",
        epilog="example usage:\n  gamelauncher.py --config example.toml"
        + "\n  WINEPREFIX= GAMEID= PROTONPATH= gamelauncher.py --exe=''",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    group: _ArgumentGroup = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", help="path to TOML file")
    group.add_argument(
        "--exe",
        help="path to game executable\nNOTE: when passing options, value must be wrapped in quotes",
    )

    return parser.parse_args(sys.argv[1:])


def _setup_pfx(path: str) -> Union[None, FileExistsError, RuntimeError]:
    """Create a symlink to the WINE prefix and tracked_files file"""
    try:
        os.symlink(path, path + "/pfx")
    except FileExistsError:
        print(f"Symbolic link already exists at {path}/pfx")
    except Exception:
        raise RuntimeError(
            "Error occurred when creating symbolic link at " + path + "/pfx"
        )
    Path(path + "/tracked_files").touch()


def check_env(env: Dict[str, str]) -> Union[None, ValueError]:
    """Before executing a game, check for environment variables"""
    if "WINEPREFIX" not in os.environ or not Path(os.environ["WINEPREFIX"]).is_dir():
        raise ValueError("Environment variable not set or not a directory: WINEPREFIX")
    path = os.environ["WINEPREFIX"]
    env["WINEPREFIX"] = path

    if "GAMEID" not in os.environ:
        raise ValueError("Environment variable not set: GAMEID")
    env["GAMEID"] = os.environ["GAMEID"]

    if "PROTONPATH" not in os.environ or not Path(os.environ["PROTONPATH"]).is_dir():
        raise ValueError("Environment variable not set or not a directory: PROTONPATH")
    env["PROTONPATH"] = os.environ["PROTONPATH"]
    env["STEAM_COMPAT_INSTALL_PATH"] = os.environ["PROTONPATH"]


def set_env(env: Dict[str, str], args: Namespace) -> Union[None, ValueError]:
    """Sets various environment variables for the Steam RT

    Expects to be invoked if not reading a TOML file
    """
    _setup_pfx(env["WINEPREFIX"])

    # Sets the environment variables: EXE and LAUNCHARGS
    for arg, val in vars(args).items():
        if arg == "exe":
            # Handle game options
            # If a game's executable follows with options, assign the options to its environment variable
            if val.find(" ") != -1:
                env["LAUNCHARGS"] = val[val.find(" ") + 1 :]
                env["EXE"] = val[: val.find(" ")]
            else:
                env["EXE"] = val


def set_env_toml(
    env: Dict[str, str], args: Namespace
) -> Union[None, KeyError, IsADirectoryError, TOMLDecodeError]:
    """Reads a TOML file then sets the environment variables for the Steam RT

    In the TOML file, certain keys map to Steam RT environment variables. For example:
          proton -> $PROTONPATH
          prefix -> $WINEPREFIX
          game_id -> $GAMEID
          launch_opts -> $LAUNCHARGS
          exe -> $EXE
    At the moment we expect the tables: 'ulwgl'
    """
    toml: Dict[str, Any] = None

    with open(vars(args).get("config"), "rb") as file:
        toml = tomllib.load(file)

    # TODO: verify if launch_opts is not a file or dir and game is a file
    # Check if 'prefix' and 'proton' values are directories and exist

    if not (
        Path(toml["ulwgl"]["prefix"]).is_dir() or Path(toml["ulwgl"]["proton"]).is_dir()
    ):
        raise NotADirectoryError(
            "Value for 'prefix' or 'proton' in TOML is not a directory."
        )

    # Set the values read from TOML to environment variables
    for key, val in toml["ulwgl"].items():
        # Handle cases for empty values
        if not val and isinstance(val, str):
            raise ValueError("Value is empty for key in TOML: " + key)
        if key == "prefix":
            env["WINEPREFIX"] = val
            _setup_pfx(val)
        elif key == "game_id":
            env["GAMEID"] = val
        elif key == "proton":
            env["PROTONPATH"] = val
            env["STEAM_COMPAT_INSTALL_PATH"] = val
        elif key == "launch_opts":
            for launch_options in val:
                if env["LAUNCHARGS"] == "":
                    env["LAUNCHARGS"] = launch_options
                else:
                    env["LAUNCHARGS"] = env["LAUNCHARGS"] + " " + launch_options
        elif key == "exe":
            # NOTE: It's possible that game options could be appended at the end
            env["EXE"] = val


def main() -> None:
    env: Dict[str, str] = {
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

    args: Namespace = parse_args()

    try:
        if vars(args).get("config"):
            set_env_toml(env, args)
        else:
            check_env(env)
            set_env(env, args)
    except Exception as err:
        print(f"{err}")
        return

    env["STEAM_COMPAT_APP_ID"] = env["GAMEID"]
    env["SteamAppId"] = env["STEAM_COMPAT_APP_ID"]
    env["STEAM_COMPAT_DATA_PATH"] = env["WINEPREFIX"]
    env["STEAM_COMPAT_SHADER_PATH"] = env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"

    # Set all environment variable
    for key, val in env.items():
        print(f"Setting environment variable: {key}={val}")
        os.environ[key] = val


if __name__ == "__main__":
    main()
