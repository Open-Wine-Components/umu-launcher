import os
from contextlib import contextmanager
from ctypes.util import find_library
from functools import lru_cache
from http.client import HTTPSConnection
from pathlib import Path
from re import Pattern
from re import compile as re_compile
from shutil import rmtree, which
from ssl import SSLContext, create_default_context
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired

from filelock import FileLock
from Xlib import display

from umu.umu_consts import STEAM_COMPAT, UMU_LOCAL
from umu.umu_log import log

ssl_context: SSLContext | None = None


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
                os.path.realpath(line[: line.rfind("/")])
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
                err: str = f"winetricks verb '{_}' is already installed in '{pfx}'"
                log.error(err)
                break

    return is_installed


def is_winetricks_verb(
    verbs: list[str], pattern: str = r"^[a-zA-Z_0-9-]+(=[a-zA-Z0-9]*)?$"
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
    launcher: Path
    lock: FileLock = FileLock(f"{UMU_LOCAL}/umu.lock")

    with lock:
        # Obsoleted files in $HOME/.local/share/umu from RC4 and below
        for file in UMU_LOCAL.glob("*"):
            is_umu_file: bool = file.name.endswith(".py") and (
                file.name.startswith(("umu", "ulwgl"))
            )
            if is_umu_file or file.name in obsoleted:
                if file.is_file():
                    file.unlink()
                if file.is_dir():
                    rmtree(str(file))

        # $HOME/.local/share/Steam/compatibilitytool.d
        launcher = STEAM_COMPAT.joinpath("ULWGL-Launcher")
        if launcher.is_dir():
            rmtree(str(launcher))

        # $HOME/.cache
        launcher = home.joinpath(".cache", "ULWGL")
        if launcher.is_dir():
            rmtree(str(launcher))

        # $HOME/.local/share
        launcher = home.joinpath(".local", "share", "ULWGL")
        if launcher.is_dir():
            rmtree(str(launcher))


@contextmanager
def https_connection(host: str):
    """Create an HTTPSConnection."""
    global ssl_context
    conn: HTTPSConnection

    if not ssl_context:
        ssl_context = create_default_context()

    conn = HTTPSConnection(host, context=ssl_context)

    if os.environ.get("UMU_LOG") == "debug":
        conn.set_debuglevel(1)

    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def xdisplay(no: str):
    """Create a Display."""
    d: display.Display = display.Display(no)

    try:
        yield d
    finally:
        d.close()
