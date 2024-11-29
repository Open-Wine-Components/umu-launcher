import os
import sys
from contextlib import contextmanager
from ctypes.util import find_library
from functools import lru_cache
from io import BufferedIOBase
from pathlib import Path
from re import Pattern
from re import compile as re_compile
from shutil import which
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired
from tarfile import open as taropen

from urllib3.response import BaseHTTPResponse
from Xlib import display

from umu.umu_consts import UMU_LOCAL
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
                err: str = (
                    f"winetricks verb '{_}' is already installed in '{pfx}'"
                )
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


@contextmanager
def xdisplay(no: str):
    """Create a Display."""
    d: display.Display = display.Display(no)

    try:
        yield d
    finally:
        d.close()


def write_file_chunks(
    path: Path,
    resp: BufferedIOBase | BaseHTTPResponse,
    # Note: hashlib._Hash is internal and an exception will be raised when imported
    hasher,  # noqa: ANN001
    chunk_size: int = 64 * 1024,
):
    """Write a file to path in chunks from a response stream while hashing it.

    Args:
        path: file path
        resp: urllib3 response streamed response
        hasher: hashlib object
        chunk_size: max size of data to read from the streamed response
    Returns:
        hashlib._Hash instance

    """
    buffer: bytearray
    view: memoryview

    if not chunk_size:
        chunk_size = 64 * 1024

    buffer = bytearray(chunk_size)
    view = memoryview(buffer)
    with path.open(mode="ab+", buffering=0) as file:
        while size := resp.readinto(buffer):
            file.write(view[:size])
            hasher.update(view[:size])

    return hasher


def extract_tarfile(path: Path, dest: Path) -> Path | None:
    """Read and securely extract a compressed TAR archive to path.

    Warns the user if unable to extract the archive securely, falling
    back to unsafe extraction. The filter used is 'tar_filter'.

    See https://docs.python.org/3/library/tarfile.html#tarfile.tar_filter
    """
    if not path.is_file():
        return None

    # Note: r:tar is a valid mode in cpython.
    # See https://github.com/python/cpython/blob/b83be9c9718aac42d0d8fc689a829d6594192afa/Lib/tarfile.py#L1871
    with taropen(path, f"r:{path.suffix.removeprefix('.')}") as tar:  # type: ignore
        try:
            from tarfile import tar_filter

            tar.extraction_filter = tar_filter
            log.debug("Using data filter for archive")
        except ImportError:
            # User is on a distro that did not backport extraction filters
            log.warning("Python: %s", sys.version)
            log.warning("Using no data filter for archive")
            log.warning("Archive will be extracted insecurely")

        log.debug("Extracting: %s -> %s", path, dest)
        tar.extractall(path=dest)  # noqa: S202

    return dest


def has_umu_setup(path: Path = UMU_LOCAL) -> bool:
    """Check if umu has been setup in our runtime directory."""
    return path.exists() and any(
        file for file in path.glob("*") if not file.name.endswith("lock")
    )
