from ctypes.util import find_library
from functools import lru_cache
from pathlib import Path
from re import Pattern, compile, match
from shutil import which
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired

from umu_log import log


@lru_cache
def get_libc() -> str:
    """Find libc.so from the user's system."""
    return find_library("c") or ""


def run_zenity(command: str, opts: list[str], msg: str) -> int:
    """Execute the command and pipe the output to zenity.

    Intended to be used for long running operations (e.g. large file downloads)
    """
    bin: str = which("zenity")
    cmd: str = which(command)
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
            zenity_proc.stdin.close()
            ret = zenity_proc.wait()

    if ret:
        log.warning("zenity exited with the status code: %s", ret)

    return ret


def _parse_winetricks_verbs(verb: str, pfx: Path) -> bool:
    """Parse the winetricks.log file."""
    wt_log: Path = pfx.joinpath("winetricks.log")
    is_installed: bool = False

    if not wt_log.is_file():
        return is_installed

    with wt_log.open(mode="r", encoding="utf-8") as file:
        for line in file:
            _: str = line.strip()
            if is_winetricks_verb(_) and _.startswith(verb):
                is_installed = True
                break

    return is_installed


@lru_cache
def is_winetricks_verb(
    verbs: str, pattern: str = r"^[a-zA-Z_0-9]+(=[a-zA-Z0-9]+)?$"
) -> bool:
    """Check if a string is a winetricks verb."""
    if verbs.find(" ") != -1:
        regex: Pattern = compile(pattern)
        return all([regex.match(verb) for verb in verbs.split()])
    return match(pattern, verbs) is not None


def is_installed_verb(verb: str, pfx: Path) -> bool:
    """Check if a winetricks verb is installed in the umu prefix."""
    return _parse_winetricks_verbs(verb, pfx)
