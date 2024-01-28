#!/usr/bin/env python3

import os
import argparse
import sys
from pathlib import Path
from tomlkit import parse


def parse_args():
    # "WINEPREFIX=$HOME/Games/epic-games-store GAMEID=egs gamelauncher.py --proton $HOME/.steam/steam/compatibilitytools.d/GE-Proton8-28 --game $HOME/Games/epic-games-store/drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe --options opengl SkipBuildPatchPrereq"
    parser = argparse.ArgumentParser(
        description="Unified Linux Wine Game Launcher",
        epilog="example usage:\n  gamelauncher.py --config example.toml"
        + "\n  WINEPREFIX= GAMEID= gamelauncher.py --proton ... --game ... --options opengl SkipBuildPatchPrereq",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--config", help="path to TOML file")
    parser.add_argument("--proton", help="path to proton directory")
    parser.add_argument("--game", help="path to game executable")
    parser.add_argument(
        "--options",
        help="launch options for game executable\nNOTE: hyphens must be omitted",
        nargs="*",
    )

    return parser.parse_args(sys.argv[1:])


# Create a symlink and tracked_files file
def _setup_pfx(path):
    try:
        os.symlink(path, path + "/pfx")
    except FileExistsError:
        print(f"Symbolic link already exists at {path}/pfx")
    Path(path + "/tracked_files").touch()


# Sets various environment variables for the Steam RT
# Expects to be invoked if not reading a TOML file
def set_env(env, args):
    if "WINEPREFIX" not in os.environ or not os.path.isdir(os.environ["WINEPREFIX"]):
        print("Environment variable not set or not a directory: WINEPREFIX")
        return
    path = os.environ["WINEPREFIX"]
    env["WINEPREFIX"] = path

    _setup_pfx(path)

    if "GAMEID" not in os.environ:
        print("Environment variable not set: GAMEID")
        return
    env["GAMEID"] = os.environ["GAMEID"]

    # Sets the environment variables: PROTONPATH, STEAM_COMPAT_INSTALL_PATH, EXE and LAUNCHARGS
    for arg, val in vars(args).items():
        if arg == "proton":
            env["PROTONPATH"] = val
            env["STEAM_COMPAT_INSTALL_PATH"] = val
        elif arg == "game":
            env["EXE"] = val
        elif arg == "options":
            # Add a hyphen to the beginning of each option
            # We're doing this because argparse cannot parse hyphenated-values
            for launch_options in val:
                if env["LAUNCHARGS"] == "":
                    env["LAUNCHARGS"] = "-" + launch_options
                else:
                    env["LAUNCHARGS"] = env["LAUNCHARGS"] + " -" + launch_options


# Reads a TOML file then sets the environment variables for the Steam RT
# When applying launch options, unlike the standard usage, no hyphens are applied
def set_env_toml(env, args):
    toml = ""

    with open(vars(args).get("config"), "r") as file:
        # This might fail. Handle it.
        toml_string = file.read()
        toml = parse(toml_string)

    if not toml.get("ulwgl"):
        raise KeyError("Table 'ulwgl' was not found in TOML file.")

    # Set the values read from TOML to environment variables
    for key, val in toml["ulwgl"].items():
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
        elif key == "game":
            env["EXE"] = val


def main():
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

    args = parse_args()

    if vars(args).get("config"):
        set_env_toml(env, args)
    else:
        set_env(env, args)

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
