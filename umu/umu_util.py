import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from ctypes.util import find_library
from fcntl import LOCK_EX, LOCK_UN, flock
from functools import lru_cache
from hashlib import new as hashnew
from io import BufferedIOBase, BufferedRandom
from pathlib import Path
from re import Pattern
from re import compile as re_compile
from shutil import which
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired
from tarfile import open as taropen
from typing import Any

from urllib3.response import BaseHTTPResponse

from umu.umu_consts import UMU_LOCAL, WINETRICKS_SETTINGS_VERBS
from umu.umu_log import log


@contextmanager
def unix_flock(path: str):
    """Create a file and configure it to be locking."""
    fd: int | None = None

    try:
        fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o644)
        # See https://man7.org/linux/man-pages/man2/flock.2.html
        flock(fd, LOCK_EX)
        yield fd
    finally:
        if fd is not None:
            flock(fd, LOCK_UN)
            os.close(fd)


@contextmanager
def memfdfile(name: str) -> Generator[BufferedRandom, Any, None]:
    """Create an anonymous file."""
    fp: BufferedRandom | None = None

    try:
        fd = os.memfd_create(name, os.MFD_CLOEXEC)
        os.set_inheritable(fd, True)
        fp = os.fdopen(fd, mode="rb+")
        yield fp
    finally:
        if fp is not None:
            fp.close()


@lru_cache
def get_libc() -> str:
    """Find libc.so from the user's system."""
    return find_library("c") or ""


@lru_cache
def get_library_paths() -> set[str]:
    """Find the shared library paths from the user's system."""
    library_paths: set[str] = set()
    paths: set[str] = set()
    ldconfig: str = which("ldconfig") or ""
    root = "/"

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
            env={"LC_ALL": "C", "LANG": "C"},
        ) as proc:
            if not proc.stdout:
                return library_paths
            for line in proc.stdout:
                lines = line.split()
                if not lines:
                    continue
                line = lines[-1]
                prefix = line[: line.rfind(root)]
                if not line.startswith(root) or prefix in paths:
                    continue
                paths.add(prefix)
                library_paths.add(os.path.realpath(prefix))
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
            line: str = line.strip()
            if line in verbs and line not in WINETRICKS_SETTINGS_VERBS:
                is_installed = True
                err: str = f"winetricks verb '{line}' is already installed in '{pfx}'"
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
            # We require Python 3.10+ and extraction filters require 3.12+
            from tarfile import tar_filter  # noqa: PLC0415

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


# Copyright (C) 2005-2010   Gregory P. Smith (greg@krypto.org)
# Licensed to PSF under a Contributor Agreement.
# Source: https://raw.githubusercontent.com/python/cpython/refs/heads/3.11/Lib/hashlib.py
# License: https://raw.githubusercontent.com/python/cpython/refs/heads/3.11/LICENSE
def file_digest(fileobj, digest, /, *, _bufsize=2**18):  # noqa: ANN001
    """Hash the contents of a file-like object. Returns a digest object.

    *fileobj* must be a file-like object opened for reading in binary mode.
    It accepts file objects from open(), io.BytesIO(), and SocketIO objects.
    The function may bypass Python's I/O and use the file descriptor *fileno*
    directly.

    *digest* must either be a hash algorithm name as a *str*, a hash
    constructor, or a callable that returns a hash object.
    """
    # On Linux we could use AF_ALG sockets and sendfile() to archive zero-copy
    # hashing with hardware acceleration.
    digestobj = hashnew(digest) if isinstance(digest, str) else digest()

    if hasattr(fileobj, "getbuffer"):
        # io.BytesIO object, use zero-copy buffer
        digestobj.update(fileobj.getbuffer())
        return digestobj

    # Only binary files implement readinto().
    if not (
        hasattr(fileobj, "readinto")
        and hasattr(fileobj, "readable")
        and fileobj.readable()
    ):
        err = f"'{fileobj!r}' is not a file-like object in binary reading mode."
        raise ValueError(err)

    # binary file, socket.SocketIO object
    # Note: socket I/O uses different syscalls than file I/O.
    buf = bytearray(_bufsize)  # Reusable buffer to reduce allocations.
    view = memoryview(buf)
    while True:
        size = fileobj.readinto(buf)
        if size == 0:
            break  # EOF
        digestobj.update(view[:size])

    return digestobj
