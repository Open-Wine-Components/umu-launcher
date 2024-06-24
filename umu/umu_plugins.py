from argparse import Namespace
from pathlib import Path
from typing import Any

from umu_log import log


def set_env_toml(
    env: dict[str, str], args: Namespace
) -> tuple[dict[str, str], list[str, tuple[str, Path]]]:
    """Read key/values in a TOML file and map them to umu env. variables.

    In the TOML file, certain keys map to environment variables:

    proton  -> $PROTONPATH
    prefix  -> $WINEPREFIX
    game_id -> $GAMEID
    exe     -> $EXE

    -which will be used as a base to create other required env variables for
    the Steam Runtime (e.g., STEAM_COMPAT_INSTALL_PATH). To note, some features
    are lost in this usage, such as running winetricks verbs and automatic
    updates to Proton.
    """
    try:
        import tomllib
    except ModuleNotFoundError:
        err: str = "tomllib requires Python 3.11"
        raise ModuleNotFoundError(err)

    # User configuration containing required key/value pairs
    toml: dict[str, Any] = None
    # Name of the configuration file
    config: Path = Path(getattr(args, "config", None)).expanduser()
    # Executable options, if any
    opts: list[str] = []

    if not config.is_file():
        err: str = f"Path to configuration is not a file: '{config}'"
        raise FileNotFoundError(err)

    with config.open(mode="rb") as file:
        toml = tomllib.load(file)

    _check_env_toml(toml)

    # Required environment variables
    env["WINEPREFIX"] = toml.get("umu").get("prefix")
    env["PROTONPATH"] = toml.get("umu").get("proton")
    env["EXE"] = toml.get("umu").get("exe")
    # Optional
    env["GAMEID"] = toml.get("umu").get("game_id", "")
    env["STORE"] = toml.get("umu").get("store", "")

    if isinstance(toml.get("umu").get("launch_args"), list):
        opts = toml["umu"]["launch_args"]
    elif isinstance(toml.get("umu").get("launch_args"), str):
        opts = toml["umu"]["launch_args"].split(" ")
    return env, opts


def _check_env_toml(toml: dict[str, Any]) -> dict[str, Any]:
    """Check for required or empty key/value pairs in user configuration file.

    Casing matters in the config and we do not check if the game id is set.
    """
    # Required table in configuration file
    table: str = "umu"
    # Required keys with their values expected to be file paths
    required_keys: list[str] = ["proton", "prefix", "exe"]

    if table not in toml:
        err: str = f"Table '{table}' in TOML is not defined."
        raise ValueError(err)

    for key in required_keys:
        path: Path = None

        if key not in toml[table]:
            err: str = (
                f"The following key in table '[{table}]' is required: {key}"
            )
            raise ValueError(err)

        path = Path(toml[table][key]).expanduser()

        # Raise an error for executables that do not exist. One case this can
        # can happen is when game options are appended at the end of the exe.
        # Users should use `launch_args` for game options
        if key == "exe" and not path.is_file():
            err: str = (
                f"Value for key '{key}' "
                f"in TOML is not a file: {toml[table][key]}"
            )
            raise FileNotFoundError(err)

        if (key == "proton" and not path.is_dir()) or (
            key == "prefix" and not path.is_dir()
        ):
            err: str = (
                f"Value for key '{key}' "
                f"in TOML is not a directory: {toml[table][key]}"
            )
            raise NotADirectoryError(err)

    # Raise an error for empty values
    for key, val in toml.get(table).items():
        if not val and isinstance(val, str):
            err: str = (
                f"Value is empty for '{key}' in TOML.\n"
                f"Please specify a value or remove the entry: '{key}={val}'"
            )
            raise ValueError(err)

    return toml
