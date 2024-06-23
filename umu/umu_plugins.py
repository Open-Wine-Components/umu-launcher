from argparse import Namespace
from pathlib import Path
from shutil import which
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired
from typing import Any

from umu_log import log


def set_env_toml(
    env: dict[str, str], args: Namespace
) -> tuple[dict[str, str], list[str]]:
    """Read a TOML file then sets the environment variables for the Steam RT.

    In the TOML file, certain keys map to Steam runtime unvironment variables.
    For example:

    proton -> $PROTONPATH
    prefix -> $WINEPREFIX
    game_id -> $GAMEID
    exe -> $EXE
    """
    try:
        import tomllib
    except ModuleNotFoundError:
        err: str = "tomllib requires Python 3.11"
        raise ModuleNotFoundError(err)

    toml: dict[str, Any] = None
    path_config: str = f"{Path(getattr(args, 'config', None)).expanduser()}"
    opts: list[str] = []

    if not Path(path_config).is_file():
        msg: str = "Path to configuration is not a file: " + getattr(
            args, "config", None
        )
        raise FileNotFoundError(msg)

    with Path(path_config).open(mode="rb") as file:
        toml = tomllib.load(file)

    _check_env_toml(toml)

    for key, val in toml["umu"].items():
        if key == "prefix":
            env["WINEPREFIX"] = val
        elif key == "game_id":
            env["GAMEID"] = val
        elif key == "proton":
            env["PROTONPATH"] = val
        elif key == "store":
            env["STORE"] = val
        elif key == "exe":
            env["EXE"] = val
        elif key == "launch_args" and isinstance(val, list):
            opts = val
        elif key == "launch_args" and isinstance(val, str):
            opts = val.split(" ")

    return env, opts


def _check_env_toml(toml: dict[str, Any]) -> dict[str, Any]:
    """Check for required or empty key/value pairs when reading a TOML config.

    Casing matters in the config and we do not check if the game id is set.
    """
    table: str = "umu"
    required_keys: list[str] = ["proton", "prefix", "exe"]

    if table not in toml:
        err: str = f"Table '{table}' in TOML is not defined."
        raise ValueError(err)

    for key in required_keys:
        if key not in toml[table]:
            err: str = (
                f"The following key in table '{table}' is required: {key}"
            )
            raise ValueError(err)

        # Raise an error for executables that do not exist
        # One case this can happen is when game options are appended at the
        # end of the exe
        # Users should use launch_args game options
        if key == "exe" and not Path(toml[table][key]).expanduser().is_file():
            val: str = toml[table][key]
            err: str = f"Value for key '{key}' in TOML is not a file: {val}"
            raise FileNotFoundError(err)

        # The proton and wine prefix need to be folders
        if (
            key == "proton"
            and not Path(toml[table][key]).expanduser().is_dir()
        ) or (
            key == "prefix"
            and not Path(toml[table][key]).expanduser().is_dir()
        ):
            dir: str = f"{Path(toml[table][key]).expanduser()}"
            err: str = (
                f"Value for key '{key}' in TOML is not a directory: {dir}"
            )
            raise NotADirectoryError(err)

    # Check for empty keys
    for key, val in toml[table].items():
        if not val and isinstance(val, str):
            err: str = (
                f"Value is empty for '{key}' in TOML.\n"
                f"Please specify a value or remove the entry:\n{key} = {val}"
            )
            raise ValueError(err)

    return toml


def enable_zenity(command: str, opts: list[str], msg: str) -> int:
    """Execute the command and pipe the output to Zenity.

    Intended to be used for long running tasks (e.g. large file downloads).
    """
    bin: str = which("zenity")
    cmd: str = which(command)

    if not bin:
        err: str = "zenity was not found in system"
        raise FileNotFoundError(err)

    if not cmd:
        err: str = f"{command} was not found in system"
        raise FileNotFoundError(err)

    with (
        Popen([cmd, *opts], stdout=PIPE, stderr=STDOUT) as proc,
        Popen(
            [
                f"{bin}",
                "--progress",
                "--auto-close",
                f"--text={msg}",
                "--percentage=0",
                "--pulsate",
                "--no-cancel",
            ],
            stdin=PIPE,
        ) as zenity_proc,
    ):
        try:
            proc.wait(timeout=300)
        except TimeoutExpired:
            zenity_proc.terminate()
            log.warning("%s timed out after 5 min.", cmd)
            raise TimeoutError

        zenity_proc.stdin.close()

        return zenity_proc.wait()
