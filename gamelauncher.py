#!/usr/bin/env python3

import os
import argparse
from argparse import ArgumentParser, _ArgumentGroup, Namespace
import sys
from pathlib import Path
import tomllib
from tomllib import TOMLDecodeError
from typing import Dict, Any, Union, List

# TODO: Only set the environment variables that are not empty
import subprocess


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


def set_env(
    env: Dict[str, str], args: Namespace
) -> Union[None, ValueError, FileNotFoundError]:
    """Sets various environment variables for the Steam RT

    Expects to be invoked if not reading a TOML file
    """
    _setup_pfx(env["WINEPREFIX"])

    # Sets the environment variables: EXE and LAUNCHARGS
    # If necessary, raise an error on invalid inputs
    for arg, val in vars(args).items():
        if arg == "exe":
            launch_args: str = ""
            exe: str = val

            # Seperate a game's launch arguments from its exe
            if val.find(" ") != -1:
                launch_args = val[val.find(" ") + 1 :]
                exe = val[: val.find(" ")]

            if not Path(exe).is_file():
                raise FileNotFoundError(f"Value for 'exe' is not a file: {exe}")

            if launch_args:
                for launch_arg in launch_args.split(" "):
                    if Path(launch_arg).is_file():
                        # There's no good reason why a launch argument should be an executable
                        raise ValueError(
                            f"Value for launch arguments should not be a file: {launch_arg}"
                        )

                env["LAUNCHARGS"] = launch_args
                env["EXE"] = exe
            else:
                env["EXE"] = exe


def set_env_toml(
    env: Dict[str, str], args: Namespace
) -> Union[None, KeyError, IsADirectoryError, TOMLDecodeError, FileNotFoundError]:
    """Reads a TOML file then sets the environment variables for the Steam RT

    In the TOML file, certain keys map to Steam RT environment variables. For example:
          proton -> $PROTONPATH
          prefix -> $WINEPREFIX
          game_id -> $GAMEID
          launch_args -> $LAUNCHARGS
          exe -> $EXE
    At the moment we expect the tables: 'ulwgl'
    """
    toml: Dict[str, Any] = None

    with Path(vars(args).get("config")).open(mode="rb") as file:
        toml = tomllib.load(file)

    if not (
        Path(toml["ulwgl"]["prefix"]).is_dir() or Path(toml["ulwgl"]["proton"]).is_dir()
    ):
        raise NotADirectoryError(
            "Value for 'prefix' or 'proton' in TOML is not a directory."
        )

    # Set the values read from TOML to environment variables
    # If necessary, raise an error on invalid inputs
    for key, val in toml["ulwgl"].items():
        # Handle cases for empty values
        if not val and isinstance(val, str):
            raise ValueError(f"Value is empty for key in TOML: {key}")
        if key == "prefix":
            env["WINEPREFIX"] = val
            _setup_pfx(val)
        elif key == "game_id":
            env["GAMEID"] = val
        elif key == "proton":
            env["PROTONPATH"] = val
            env["STEAM_COMPAT_INSTALL_PATH"] = val
        elif key == "launch_args":
                    # There's no good reason why a launch argument should be an executable
                    raise ValueError(
                        f"Value for launch arguments should not be a file: {launch_options}"
                    )

                if env["LAUNCHARGS"] == "":
                    env["LAUNCHARGS"] = launch_options
                else:
                    env["LAUNCHARGS"] = env["LAUNCHARGS"] + " " + launch_options
        elif key == "exe":
            # Raise an error for executables that do not exist
            if not Path(val).is_file():
                raise FileNotFoundError("Value for key 'exe' in TOML is not a file.")

            # NOTE: It's possible that game options could be appended at the end
            env["EXE"] = val


def build_command(
    env: Dict[str, str], command: List[str]
) -> Union[None, FileNotFoundError]:
    """Build the command to be executed"""
    verb: str = "waitforexitandrun"
    # NOTE: We must assume _v2-entry-point (ULWGL) is within the same dir as this launcher
    # Otherwise, an error can be raised
    entry_point: str = Path(Path(__file__).cwd().as_posix() + "/ULWGL").as_posix()

    if not Path(env.get("PROTONPATH") + "/proton").is_file():
        raise FileNotFoundError(
            "The following file was not found in PROTONPATH: proton"
        )

    command.extend([entry_point, "--verb", verb, "--"])
    if env.get("LAUNCHARGS"):
        command.extend(
            [
                Path(env.get("PROTONPATH") + "/proton").as_posix(),
                verb,
                env.get("EXE"),
                env.get("LAUNCHARGS"),
            ]
        )
    else:
        command.extend(
            [Path(env.get("PROTONPATH") + "/proton").as_posix(), verb, env.get("EXE")]
        )


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
    command: List[str] = []

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
    # NOTE: `env` after this block should be read only
    for key, val in env.items():
        print(f"Setting environment variable: {key}={val}")
        os.environ[key] = val

    build_command(env, command)
    print(f"The following command will be executed: {command}")
    subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True)


if __name__ == "__main__":
    main()
