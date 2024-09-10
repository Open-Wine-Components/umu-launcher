import os
from ctypes.util import find_library
from functools import lru_cache
from pathlib import Path
from re import Pattern
from re import compile as re_compile
from shutil import which
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired

from umu.umu_consts import STEAM_COMPAT, UMU_LOCAL
from umu.umu_log import log


@lru_cache
def get_libc() -> str:
    """Find libc.so from the user's system."""
    return find_library("c") or ""


@lru_cache
def get_library_paths() -> set[str]:
    """Find the shared library paths from the user's system."""
    library_paths: set[str] = set()
    ldconfig: str = which("ldconfig") or ""

    if not ldconfig:
        log.warning("ldconfig not found in $PATH, cannot find library paths")
        return library_paths

    # Find all shared library path prefixes within the assumptions of the
    # Steam Runtime container framework. The framework already works hard by
    # attempting to work with various distibutions' quirks. Unless it's Flatpak
    # related, let's continue to make it their job.
    try:
        # Here, opt to using the ld.so cache similar to the stdlib
        # implementation of _findSoname_ldconfig.
        with Popen(
            (ldconfig, "-p"),
            text=True,
            encoding="utf-8",
            stdout=PIPE,
            stderr=PIPE,
            env={"LC_ALL": "C", "LANG": "C"},
        ) as proc:
            stdout, _ = proc.communicate()
            library_paths |= {
                line[: line.rfind("/")]
                for line in stdout.split()
                if line.startswith("/")
            }
    except OSError as e:
        log.exception(e)

    return library_paths


def run_zenity(command: str, opts: list[str], msg: str) -> int:
    """Execute the command and pipe the output to zenity.

    Intended to be used for long running operations (e.g. large file downloads)
    """
    zenity: str = which("zenity") or ""
    cmd: str = which(command) or ""
    ret: int = 0  # Exit code returned from zenity

    if not zenity:
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
                f"{zenity}",
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
    regex = re_compile(pattern)
    for verb in verbs:
        if not regex.match(verb):
            err: str = f"Value is not a winetricks verb: '{verb}'"
            log.error(err)
            return False

    return True


def find_obsolete() -> None:
    """Find obsoleted launcher files and log them."""
    home: Path = Path.home()
    obsoleted: set[str] = {
        "reaper",
        "sniper_platform_0.20240125.75305",
        "BUILD_ID.txt",
        "umu_version.json",
        "sniper_platform_0.20231211.70175",
    }

    # Obsoleted files in $HOME/.local/share/umu from RC4 and below
    for file in UMU_LOCAL.glob("*"):
        is_umu_file: bool = file.name.endswith(".py") and (
            file.name.startswith(("umu", "ulwgl"))
        )
        if is_umu_file or file.name in obsoleted:
            log.warning("'%s' is obsolete", file)

    # $HOME/.local/share/Steam/compatibilitytool.d
    if (launcher := STEAM_COMPAT.joinpath("ULWGL-Launcher")).is_dir():
        log.warning("'%s' is obsolete", launcher)

    # $HOME/.cache
    if (cache := home.joinpath(".cache", "ULWGL")).is_dir():
        log.warning("'%s' is obsolete", cache)

    # $HOME/.local/share
    if (ulwgl := home.joinpath(".local", "share", "ULWGL")).is_dir():
        log.warning("'%s' is obsolete", ulwgl)


def get_osrelease_id() -> str:
    """Get the identity of the host OS."""
    release: Path
    osid: str = ""

    # Flatpak follows the Container Interface outlined by systemd
    # See https://systemd.io/CONTAINER_INTERFACE
    if os.environ.get("container") == "flatpak":  # noqa: SIM112
        release = Path("/run/host/os-release")
    else:
        release = Path("/etc/os-release")

    if not release.is_file():
        log.debug("File '%s' could not be found", release)
        return osid

    with release.open(mode="r", encoding="utf-8") as file:
        for line in file:
            if line.startswith("ID="):
                osid = line.removeprefix("ID=").strip()
                log.debug("OS: %s", osid)
                break

    return osid
