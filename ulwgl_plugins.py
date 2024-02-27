import os
from pathlib import Path
from typing import Dict, Set, Any, List
from argparse import Namespace


def set_env_toml(env: Dict[str, str], args: Namespace) -> Dict[str, str]:
    """Read a TOML file then sets the environment variables for the Steam RT.

    In the TOML file, certain keys map to Steam RT environment variables. For example:
          proton -> $PROTONPATH
          prefix -> $WINEPREFIX
          game_id -> $GAMEID
          exe -> $EXE
    At the moment we expect the tables: 'ulwgl'
    """
    try:
        import tomllib
    except ModuleNotFoundError:
        msg: str = "tomllib requires Python 3.11"
        raise ModuleNotFoundError(msg)

    toml: Dict[str, Any] = None
    path_config: str = Path(getattr(args, "config", None)).expanduser().as_posix()

    if not Path(path_config).is_file():
        msg: str = "Path to configuration is not a file: " + getattr(
            args, "config", None
        )
        raise FileNotFoundError(msg)

    with Path(path_config).open(mode="rb") as file:
        toml = tomllib.load(file)

    _check_env_toml(env, toml)

    for key, val in toml["ulwgl"].items():
        if key == "prefix":
            env["WINEPREFIX"] = val
        elif key == "game_id":
            env["GAMEID"] = val
        elif key == "proton":
            env["PROTONPATH"] = val
        elif key == "store":
            env["STORE"] = val
        elif key == "exe":
            if toml.get("ulwgl").get("launch_args"):
                env["EXE"] = val + " " + " ".join(toml.get("ulwgl").get("launch_args"))
            else:
                env["EXE"] = val
    return env


def _check_env_toml(env: Dict[str, str], toml: Dict[str, Any]):
    """Check for required or empty key/value pairs when reading a TOML config.

    NOTE: Casing matters in the config and we do not check if the game id is set
    """
    table: str = "ulwgl"
    required_keys: List[str] = ["proton", "prefix", "exe"]

    if table not in toml:
        err: str = f"Table '{table}' in TOML is not defined."
        raise ValueError(err)

    for key in required_keys:
        if key not in toml[table]:
            err: str = f"The following key in table '{table}' is required: {key}"
            raise ValueError(err)

        # Raise an error for executables that do not exist
        # One case this can happen is when game options are appended at the end of the exe
        # Users should use launch_args for that
        if key == "exe" and not Path(toml[table][key]).expanduser().is_file():
            val: str = toml[table][key]
            err: str = f"Value for key '{key}' in TOML is not a file: {val}"
            raise FileNotFoundError(err)

        # The proton and wine prefix need to be folders
        if (key == "proton" and not Path(toml[table][key]).expanduser().is_dir()) or (
            key == "prefix" and not Path(toml[table][key]).expanduser().is_dir()
        ):
            dir: str = Path(toml[table][key]).expanduser().as_posix()
            err: str = f"Value for key '{key}' in TOML is not a directory: {dir}"
            raise NotADirectoryError(err)

    # Check for empty keys
    for key, val in toml[table].items():
        if not val and isinstance(val, str):
            err: str = f"Value is empty for '{key}' in TOML.\nPlease specify a value or remove the following entry:\n{key} = {val}"
            raise ValueError(err)

    return toml


def enable_steam_game_drive(env: Dict[str, str]) -> Dict[str, str]:
    """Enable Steam Game Drive functionality.

    Expects STEAM_COMPAT_INSTALL_PATH to be set
    STEAM_RUNTIME_LIBRARY_PATH will not be set if the exe directory does not exist
    """
    paths: Set[str] = set()
    root: Path = Path("/")

    # Check for mount points going up toward the root
    # NOTE: Subvolumes can be mount points
    for path in Path(env["STEAM_COMPAT_INSTALL_PATH"]).parents:
        if path.is_mount() and path != root:
            if env["STEAM_COMPAT_LIBRARY_PATHS"]:
                env["STEAM_COMPAT_LIBRARY_PATHS"] = (
                    env["STEAM_COMPAT_LIBRARY_PATHS"] + ":" + path.as_posix()
                )
            else:
                env["STEAM_COMPAT_LIBRARY_PATHS"] = path.as_posix()
            break

    if "LD_LIBRARY_PATH" in os.environ:
        paths.add(Path(os.environ["LD_LIBRARY_PATH"]).as_posix())

    if env["STEAM_COMPAT_INSTALL_PATH"]:
        paths.add(env["STEAM_COMPAT_INSTALL_PATH"])

    # Hard code for now because these paths seem to be pretty standard
    # This way we avoid shelling to ldconfig
    paths.add("/usr/lib")
    paths.add("/usr/lib32")
    env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(list(paths))

    return env
