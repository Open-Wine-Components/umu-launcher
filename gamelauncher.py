#!/usr/bin/env python3

import os
import argparse
from argparse import ArgumentParser, _ArgumentGroup, Namespace
import sys
from pathlib import Path
import tomllib
from typing import Dict, Any, List, Set
import gamelauncher_plugins

# TODO: Only set the environment variables that are not empty
import subprocess


def parse_args() -> Namespace:  # noqa: D103
    exe: str = Path(__file__).name
    usage: str = """
  example usage:
  {} --config example.toml
  {} --config /home/foo/example.toml --options '-opengl'
  WINEPREFIX= GAMEID= PROTONPATH= {} --exe /home/foo/example.exe --options '-opengl'
  WINEPREFIX= GAMEID= PROTONPATH= {} --exe ""
  WINEPREFIX= GAMEID= PROTONPATH= {} --exe /home/foo/example.exe --verb waitforexitandrun
    """.format(exe, exe, exe, exe, exe)

    parser: ArgumentParser = argparse.ArgumentParser(
        description="Unified Linux Wine Game Launcher",
        epilog=usage,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    group: _ArgumentGroup = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config", help="path to TOML file")
    group.add_argument(
        "--exe",
        help="path to game executable\npass an empty string to create a prefix",
        default=None,
    )
    parser.add_argument(
        "--verb",
        help="a verb to pass to Proton (default: waitforexitandrun)",
    )
    parser.add_argument(
        "--options",
        help="launch options for game executable\nNOTE: options must be wrapped in quotes",
    )

    return parser.parse_args(sys.argv[1:])


def _setup_pfx(path: str) -> None:
    """Create a symlink to the WINE prefix and tracked_files file."""
    if not (Path(path + "/pfx")).expanduser().is_symlink():
        # When creating the symlink, we want it to be in expanded form when passed unexpanded paths
        # Example: pfx -> /home/.wine
        Path(path + "/pfx").expanduser().symlink_to(Path(path).expanduser())
    Path(path + "/tracked_files").expanduser().touch()


def check_env(env: Dict[str, str]) -> Dict[str, str]:
    """Before executing a game, check for environment variables and set them.

    WINEPREFIX, GAMEID and PROTONPATH are strictly required.
    """
    if "WINEPREFIX" not in os.environ:
        err: str = "Environment variable not set or not a directory: WINEPREFIX"
        raise ValueError(err)

    if not Path(os.environ["WINEPREFIX"]).expanduser().is_dir():
        Path(os.environ["WINEPREFIX"]).mkdir(parents=True)
    env["WINEPREFIX"] = os.environ["WINEPREFIX"]

    if "GAMEID" not in os.environ:
        err: str = "Environment variable not set: GAMEID"
        raise ValueError(err)
    env["GAMEID"] = os.environ["GAMEID"]

    if (
        "PROTONPATH" not in os.environ
        or not Path(os.environ["PROTONPATH"]).expanduser().is_dir()
    ):
        err: str = "Environment variable not set or not a directory: PROTONPATH"
        raise ValueError(err)
    env["PROTONPATH"] = os.environ["PROTONPATH"]
    env["STEAM_COMPAT_INSTALL_PATH"] = os.environ["PROTONPATH"]

    return env


def set_env(env: Dict[str, str], args: Namespace) -> Dict[str, str]:
    """Set various environment variables for the Steam RT.

    Expects to be invoked if not reading a TOML file
    """
    _setup_pfx(env["WINEPREFIX"])
    is_create_prefix: bool = False

    if not getattr(args, "exe", None):
        is_create_prefix = True

    # Sets the environment variables: EXE
    for arg, val in vars(args).items():
        if arg == "exe" and not is_create_prefix:
            # NOTE: options can possibly be appended at the end
            env["EXE"] = val
        elif arg == "options" and val and not is_create_prefix:
            # NOTE: assume it's space separated
            env["EXE"] = env["EXE"] + " " + " ".join(val.split(" "))

    return env


def set_env_toml(env: Dict[str, str], args: Namespace) -> Dict[str, str]:
    """Read a TOML file then sets the environment variables for the Steam RT.

    In the TOML file, certain keys map to Steam RT environment variables. For example:
          proton -> $PROTONPATH
          prefix -> $WINEPREFIX
          game_id -> $GAMEID
          exe -> $EXE
    At the moment we expect the tables: 'ulwgl'
    """
    toml: Dict[str, Any] = None
    path_config: str = Path(getattr(args, "config", None)).expanduser().as_posix()

    if not Path(path_config).is_file():
        msg: str = "Path to configuration is not a file: " + getattr(
            args, "config", None
        )
        raise FileNotFoundError(msg)

    with Path(path_config).open(mode="rb") as file:
        toml = tomllib.load(file)

    if not (
        Path(toml["ulwgl"]["prefix"]).expanduser().is_dir()
        or Path(toml["ulwgl"]["proton"]).expanduser().is_dir()
    ):
        err: str = "Value for 'prefix' or 'proton' in TOML is not a directory."
        raise NotADirectoryError(err)

    # Set the values read from TOML to environment variables
    # If necessary, raise an error on invalid inputs
    for key, val in toml["ulwgl"].items():
        # Handle cases for empty values
        if not val and isinstance(val, str):
            err: str = "Value is empty for key in TOML: " + key
            raise ValueError(err)
        if key == "prefix":
            env["WINEPREFIX"] = val
            _setup_pfx(val)
        elif key == "game_id":
            env["GAMEID"] = val
        elif key == "proton":
            env["PROTONPATH"] = val
            env["STEAM_COMPAT_INSTALL_PATH"] = val
        elif key == "exe":
            # Raise an error for executables that do not exist
            # One case this can happen is when game options are appended at the end of the exe
            if not Path(val).expanduser().is_file():
                err: str = "Value for key 'exe' in TOML is not a file."
                raise FileNotFoundError(err)

            # It's possible for users to pass values to --options
            # Add any if they exist
            if toml.get("ulwgl").get("launch_args"):
                env["EXE"] = val + " " + " ".join(toml.get("ulwgl").get("launch_args"))
            else:
                env["EXE"] = val

            if getattr(args, "options", None):
                # Assume space separated options and just trust it
                env["EXE"] = (
                    env["EXE"]
                    + " "
                    + " ".join(getattr(args, "options", None).split(" "))
                )

    return env


def build_command(env: Dict[str, str], command: List[str], verb: str) -> List[str]:
    """Build the command to be executed."""
    # NOTE: We must assume _v2-entry-point (ULWGL) is within the same dir as this launcher
    # Otherwise, an error can be raised
    entry_point: str = Path(Path(__file__).cwd().as_posix() + "/ULWGL").as_posix()

    if not Path(env.get("PROTONPATH") + "/proton").is_file():
        err: str = "The following file was not found in PROTONPATH: proton"
        raise FileNotFoundError(err)

    command.extend([entry_point, "--verb", verb, "--"])
    command.extend(
        [Path(env.get("PROTONPATH") + "/proton").as_posix(), verb, env.get("EXE")]
    )

    return command


def main() -> None:  # noqa: D103
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
        "SteamAppId": "",
        "SteamGameId": "",
        "STEAM_RUNTIME_LIBRARY_PATH": "",
    }
    command: List[str] = []
    verb: str = "waitforexitandrun"
    # Represents a valid list of current supported Proton verbs
    verbs: Set[str] = {
        "waitforexitandrun",
        "run",
        "runinprefix",
        "destroyprefix",
        "getcompatpath",
        "getnativepath",
    }
    args: Namespace = parse_args()

    if getattr(args, "config", None):
        set_env_toml(env, args)
    else:
        check_env(env)
        set_env(env, args)

    if getattr(args, "verb", None) and getattr(args, "verb", None) in verbs:
        verb = getattr(args, "verb", None)

    env["STEAM_COMPAT_APP_ID"] = env["GAMEID"]
    env["SteamAppId"] = env["STEAM_COMPAT_APP_ID"]
    env["SteamGameId"] = env["SteamAppId"]
    env["WINEPREFIX"] = Path(env["WINEPREFIX"]).expanduser().as_posix()
    env["PROTONPATH"] = Path(env["PROTONPATH"]).expanduser().as_posix()
    env["STEAM_COMPAT_DATA_PATH"] = env["WINEPREFIX"]
    env["STEAM_COMPAT_SHADER_PATH"] = env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
    env["STEAM_COMPAT_INSTALL_PATH"] = Path(env["EXE"]).parent.expanduser().as_posix()
    env["EXE"] = Path(env["EXE"]).expanduser().as_posix()
    env["STEAM_COMPAT_TOOL_PATHS"] = (
        env["PROTONPATH"] + ":" + Path(__file__).parent.as_posix()
    )
    env["STEAM_COMPAT_MOUNTS"] = env["STEAM_COMPAT_TOOL_PATHS"]

    # Create an empty Proton prefix when asked
    if not getattr(args, "exe", None) and not getattr(args, "config", None):
        env["EXE"] = ""
        env["STEAM_COMPAT_INSTALL_PATH"] = ""
        verb = "waitforexitandrun"

    # Game Drive functionality
    gamelauncher_plugins.enable_steam_game_drive(env)

    # Set all environment variable
    # NOTE: `env` after this block should be read only
    for key, val in env.items():
        print(f"Setting environment variable: {key}={val}")
        os.environ[key] = val

    build_command(env, command, verb)
    print(f"The following command will be executed: {command}")
    subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True)


if __name__ == "__main__":
    main()
