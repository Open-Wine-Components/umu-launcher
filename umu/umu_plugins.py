from argparse import Namespace
from pathlib import Path
from typing import Any
from string import Template

def set_env_toml(
    env: dict[str, str], args: Namespace
) -> tuple[dict[str, str], list[str]]:
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
        # Ignore. We require Python 3.10+ and tomllib requires 3.11+
        import tomllib  # noqa: PLC0415
    except ModuleNotFoundError:
        err: str = "tomllib requires Python 3.11"
        raise ModuleNotFoundError(err)

    # User configuration containing required key/value pairs
    toml: dict[str, Any]
    # Configuration file path
    config_path: Path
    # Name of the configuration file
    config: str = getattr(args, "config", "")
    # Executable options, if any
    opts: list[str] = []

    if not config:
        err: str = f"Property 'config' does not exist in type '{type(args)}'"
        raise AttributeError(err)

    config_path = Path(config).expanduser()

    if not config_path.is_file():
        err: str = f"Path to configuration is not a file: '{config}'"
        raise FileNotFoundError(err)

    with config_path.open(mode="rb") as file:
        toml = tomllib.load(file)

    _check_toml(toml)

    # Required environment variables
    env["WINEPREFIX"] = toml["umu"]["prefix"]
    env["PROTONPATH"] = toml["umu"]["proton"]
    env["EXE"] = toml["umu"]["exe"]
    # Optional
    env["GAMEID"] = toml["umu"].get("game_id", "")
    env["STORE"] = toml["umu"].get("store", "")

    # Add config file dir to env so it can be referenced
    env["UMU_CONFIG_FILE_DIR"] = str(config_path.parent)

    # Perform expansion of env vars for paths
    env["WINEPREFIX"] = Template(env["WINEPREFIX"]).safe_substitute(env)
    env["PROTONPATH"] = Template(env["PROTONPATH"]).safe_substitute(env)
    env["EXE"] = Template(env["EXE"]).safe_substitute(env)

    _check_env(env)

    if isinstance(toml["umu"].get("launch_args"), list):
        opts = toml["umu"]["launch_args"]
    elif isinstance(toml["umu"].get("launch_args"), str):
        opts = toml["umu"]["launch_args"].split(" ")

    return env, opts


def _check_toml(toml: dict[str, Any]) -> dict[str, Any]:
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
        path: Path

        if key not in toml[table]:
            err: str = f"The following key in table '[{table}]' is required: '{key}'"
            raise ValueError(err)

        path = Path(toml[table][key]).expanduser()

        
    # Raise an error for empty values
    for key, val in toml[table].items():
        if not val and isinstance(val, str):
            err: str = (
                f"Value is empty for '{key}'.\n"
                f"Please specify a value or remove the entry: '{key}={val}'"
            )
            raise ValueError(err)

    return toml

def _check_env(env: dict[str, str]):
    # Raise an error for executables that do not exist. One case this can
    # can happen is when game options are appended at the end of the exe.
    # Users should use `launch_args` for game options
    if not Path(env["EXE"]).is_file():
        err: str = f"Value for key '{key}' is not a file: '{toml[table][key]}'"
        raise FileNotFoundError(err)

    if not Path(env["PROTONPATH"]).is_dir() or not Path(env["WINEPREFIX"]):
        err: str = f"Value for key '{key}' is not a directory: '{toml[table][key]}'"
        raise NotADirectoryError(err)

