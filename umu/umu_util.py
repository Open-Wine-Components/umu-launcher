import os
from ctypes.util import find_library
from functools import lru_cache
from json import load
from pathlib import Path
from re import Pattern, compile
from shutil import which
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired
from typing import Any

from umu_log import log


@lru_cache
def get_libc() -> str:
    """Find libc.so from the user's system."""
    return find_library("c") or ""


def run_zenity(command: str, opts: list[str], msg: str) -> int:
    """Execute the command and pipe the output to zenity.

    Intended to be used for long running operations (e.g. large file downloads)
    """
    bin: str = which("zenity") or ""
    cmd: str = which(command) or ""
    ret: int = 0  # Exit code returned from zenity

    if not bin:
        log.warning("zenity was not found in system")
        return -1

    if not cmd:
        log.warning("%s was not found in system", command)
        return -1

    # Communicate a process with zenity
    with (  # noqa: SIM117
        Popen(
            [cmd, *opts],
            stdout=PIPE,
            stderr=STDOUT,
        ) as proc,
    ):
        with Popen(
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
        ) as zenity_proc:
            try:
                proc.wait(timeout=300)
            except TimeoutExpired:
                zenity_proc.terminate()
                log.warning("%s timed out after 5 min.", cmd)
                raise TimeoutError

            if zenity_proc.stdin:
                zenity_proc.stdin.close()

            ret = zenity_proc.wait()

    if ret:
        log.warning("zenity exited with the status code: %s", ret)

    return ret


def is_installed_verb(verb: list[str], pfx: Path) -> bool:
    """Check if a winetricks verb is installed in the umu prefix.

    Determines the installation of verbs by reading winetricks.log file.
    """
    wt_log: Path
    verbs: set[str]
    is_installed: bool = False

    if not pfx:
        err: str = f"Value is '{pfx}' for WINE prefix"
        raise FileNotFoundError(err)

    if not verb:
        err: str = "winetricks was passed an empty verb"
        raise ValueError(err)

    wt_log = pfx.joinpath("winetricks.log")
    verbs = set(verb)

    if not wt_log.is_file():
        return is_installed

    with wt_log.open(mode="r", encoding="utf-8") as file:
        for line in file:
            _: str = line.strip()
            if _ in verbs:
                is_installed = True
                err: str = (
                    f"winetricks verb '{_}' is already installed in '{pfx}'"
                )
                log.error(err)
                break

    return is_installed


def is_winetricks_verb(
    verbs: list[str], pattern: str = r"^[a-zA-Z_0-9]+(=[a-zA-Z0-9]*)?$"
) -> bool:
    """Check if a string is a winetricks verb."""
    regex: Pattern

    if not verbs:
        return False

    # When passed a sequence, check each verb and log the non-verbs
    regex = compile(pattern)
    for verb in verbs:
        if not regex.match(verb):
            err: str = f"Value is not a winetricks verb: '{verb}'"
            log.error(err)
            return False

    return True


@lru_cache
def is_steamdeck() -> bool:
    """Determine if the host device is a Steam Deck by its CPU model."""
    cpu_info: Path = Path("/proc/cpuinfo")
    is_sd: bool = False
    sd_models: set[str] = {"AMD Custom APU 0405", "AMD Custom APU 0932"}

    if not cpu_info.is_file():
        return is_sd

    with cpu_info.open(mode="r", encoding="utf-8") as file:
        for line in file:
            if line.startswith("model name"):
                _: str = line[line.find(":") + 1 :].strip()
                if _ in sd_models:
                    is_sd = True
                    break

    return is_sd


def _parse_gogcfg(env: os._Environ[str]) -> Path | None:
    json: dict[str, Any]
    gog_info: Path
    subdir: Path | None = None
    install_dir: Path = Path(env["STEAM_COMPAT_INSTALL_PATH"])

    if not install_dir.is_dir():
        return None

    try:
        # Assume that there's only 1 *.info file in the game dir
        gog_info = max(
            file
            for file in install_dir.glob("*.info")
            if file.name.startswith("goggame")
        )
    except ValueError:
        log.debug("No *.info files were found in '%s'", install_dir)
        return None

    with gog_info.open(mode="r", encoding="utf-8") as file:
        json = load(file)

    if not json:
        log.debug("File '%s' is empty", gog_info)
        log.debug("Will not change to a subdirectory")
        return None

    if "playTasks" not in json:
        log.debug("File '%s' does not have a 'playTasks' property", gog_info)
        log.debug("Will not change to a subdirectory")
        return None

    # Get the first result and assume it's the correct one
    for item in json["playTasks"]:
        if (path := item.get("path")) and len(
            subpaths := Path(path).parts
        ) > 1:
            subdir = Path(*subpaths[:-1])
            log.debug(
                "Found subdirectory '%s'",
                subdir,
            )
            break

    return subdir


def find_subdir(env: os._Environ[str]) -> Path | None:
    """Find the correct directory to run the executable by parsing a file.

    Some games require to be executed in a specific way, by either requiring
    the path to be relative or to be in a subdirectory within the game
    directory. Otherwise, the game may fail to run. The correct subdirectory
    is usually defined within a configuration file by the developer (e.g.,
    installscript.vdf or *.info files).
    """
    subdir: Path | None
    store: str = env["STORE"]

    # TODO: Parse Steam's .vdf files.
    match store:
        # For GOG, metadata is in *.info files
        case "gog":
            log.debug("GOG store detected")
            subdir = _parse_gogcfg(env)
        case _:
            subdir = None

    return subdir
