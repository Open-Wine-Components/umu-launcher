import errno
import os
import sys
from collections.abc import Generator
from contextlib import contextmanager
from ctypes import CDLL, get_errno
from ctypes.util import find_library
from enum import IntFlag
from fcntl import LOCK_EX, LOCK_UN, flock
from functools import cache
from hashlib import new as hashnew
from io import BufferedIOBase, BufferedRandom
from pathlib import Path
from re import Pattern
from re import compile as re_compile
from shutil import which
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired  # nosec B404
from tarfile import open as taropen
from tempfile import gettempdir, mkdtemp
from typing import Any

from urllib3.response import BaseHTTPResponse
from Xlib import display

from umu.umu_consts import TMPFS_MIN, UMU_CACHE, UMU_LOCAL, WINETRICKS_SETTINGS_VERBS
from umu.umu_log import log


class Renameat2(IntFlag):
    """Represent a supported bit mask flag for renameat2.

    See https://www.man7.org/linux/man-pages/man2/rename.2.html
    """

    RENAME_EXCHANGE = 2
    # Don't overwrite DEST of the rename and error if DEST already exists.
    # See rename(2) for supported file systems and Linux kernel versions.
    RENAME_NOREPLACE = 1
    # Creates a "whiteout" object at the source of the rename at the same time as
    # performing the rename. See renameat(2) for details.
    # Requires Linux 3.18+
    RENAME_WHITEOUT = 4


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


@cache
def get_libc() -> str:
    """Find libc.so from the user's system."""
    return find_library("c") or ""


@cache
def get_library_paths() -> set[str]:
    """Find the shared library paths from the user's system."""
    library_paths: set[str] = set()
    paths: set[str] = set()
    ldconfig_paths: str = ":".join(filter(None, (os.environ.get("PATH"), "/sbin")))
    ldconfig: str = which("ldconfig", path=ldconfig_paths) or ""
    root = "/"

    ldconfig_path = which(ldconfig)
    if ldconfig_path is None:
        log.warning("ldconfig not found in $PATH, cannot find library paths")
        return library_paths

    # Find all shared library path prefixes within the assumptions of the
    # Steam Runtime container framework. The framework already works hard by
    # attempting to work with various distibutions' quirks. Unless it's Flatpak
    # related, let's continue to make it their job.
    try:
        # Here, opt to using the ld.so cache similar to the stdlib
        # implementation of _findSoname_ldconfig.
        with Popen(  # nosec B603
            (ldconfig_path, "-p"),
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
    ret: int = 0  # Exit code returned from zenity

    zenity_path: str | None = which("zenity")
    if zenity_path is None:
        log.warning("zenity was not found in system")
        return -1

    cmd_path: str | None = which(command)
    if cmd_path is None:
        log.warning("%s was not found in system", command)
        return -1

    zenity: str = zenity_path
    cmd: str = cmd_path

    # Communicate a process with zenity
    with (  # noqa: SIM117
        Popen(  # nosec B603
            [cmd, *opts],
            stdout=PIPE,
            stderr=STDOUT,
        ) as proc,
    ):
        with Popen(  # nosec B603
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


@contextmanager
def xdisplay(no: str):
    """Create a Display."""
    d: display.Display | None = None

    try:
        d = display.Display(no)
        yield d
    finally:
        if d is not None:
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


def _get_lines_split(
    path: Path, sep: str | None, maxsplit: int = -1
) -> Generator[list[str], Any, None]:
    with path.open(mode="r", encoding="utf-8") as file:
        lines = iter(line.split(sep=sep, maxsplit=maxsplit) for line in file)
        yield from (columns for columns in lines if columns)


@cache
def _get_supported_fs() -> set[str]:
    # https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/4/html/reference_guide/s2-proc-filesystems
    return {line[-1] for line in _get_lines_split(Path("/proc/filesystems"), None, 2)}


@cache
def _fsck_path(path: Path, filesystem: str) -> bool:
    """Validate the file system of a path."""
    if filesystem not in _get_supported_fs():
        log.error("Path is not a supported Linux file system: %s", filesystem)
        return False

    # https://docs.kernel.org/filesystems/proc.html#kernel-data
    # https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/4/html/introduction_to_system_administration/s4-storage-mounting-proc
    lines = _get_lines_split(Path("/proc/mounts"), None, 5)
    dst = str(path)

    return any(line for line in lines if line[1] == dst and line[2] == filesystem)


def get_tempdir(cache: Path = UMU_CACHE) -> Path:
    """Get a path to a temporary directory on a tmpfs.

    The temporary directory is created securely, and the path returned may be
    on a tmpfs. For a temporary directory to be on a tmpfs, the destination
    mount point must be >= TMPFS_MIN. Otherwise, file system at $XDG_CACHE_HOME
    will be used to create the temporary directory.
    """
    tmpdir = Path(gettempdir())

    # Fallback to the cache instead of the current working directory
    # https://github.com/python/cpython/blob/f297a2292cd3c3596f21ca5914310f1f8d5d8750/Lib/tempfile.py#L175
    if tmpdir == Path.cwd():
        tmpdir = cache

    stat = os.statvfs(tmpdir)
    has_tmpfs_min = (
        _fsck_path(tmpdir, "tmpfs") and stat.f_frsize * stat.f_blocks >= TMPFS_MIN
    )

    # Return without handling the case where the cache is a tmpfs
    return Path(mkdtemp()) if has_tmpfs_min else Path(mkdtemp(prefix=".", dir=cache))


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
        file for file in path.glob("**/*") if file.is_file() and not file.name.endswith("lock")
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


def _renameat2(
    olddirfd: int,
    oldpath: str,
    newdirfd: int,
    newpath: str,
    flags: Renameat2,
) -> None:
    # Load libc with errno tracking enabled
    libc: CDLL = CDLL(get_libc(), use_errno=True)

    ret = libc.renameat2(olddirfd, oldpath.encode(), newdirfd, newpath.encode(), flags)
    if ret == 0:
        return

    err = get_errno()
    raise OSError(err, os.strerror(err), oldpath, None, newpath)


def _renameat2_fallback(src: os.PathLike, dest: os.PathLike, flags: int) -> None:
    """Fallback implementation for renameat2.

    Supports:
        - plain rename
        - RENAME_EXCHANGE (best-effort, not atomic on NFS)
    """
    src = Path(src)
    dest = Path(dest)

    if flags == 0:
        # Simple rename fallback
        src.replace(dest)
        return

    if flags == Renameat2.RENAME_EXCHANGE:
        # Best-effort exchange fallback
        tmp = dest.with_name(dest.name + ".renameat2-tmp")

        # dest -> tmp
        dest.replace(tmp)
        try:
            # src -> dest
            src.replace(dest)
            # tmp -> src
            tmp.replace(src)
        except Exception:
            # Try to restore original state
            try:
                if dest.exists():
                    dest.replace(src)
            finally:
                if tmp.exists():
                    tmp.replace(dest)
            raise

        return

    raise OSError(errno.ENOTSUP, "renameat2 flags not supported by fallback")


@contextmanager
def _split_dirfd(path: os.PathLike) -> Generator[tuple[int, str], Any, None]:
    fd: int | None = None
    path = Path(path)

    try:
        fd = os.open(path.parent, os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC)
        yield (fd, path.name)
    finally:
        if fd is not None:
            os.close(fd)


def renameat2(src: os.PathLike, dest: os.PathLike, flags: Renameat2) -> None:
    """Rename a file using the renameat2 system call, with fallback."""
    with _split_dirfd(src) as src_split, _split_dirfd(dest) as dst_split:
        try:
            # Note, renameat2 requires Linux 3.15 and glibc 2.28. Our minimum target
            # platform is latest Debian, which will have versions 3.15+ and 2.28+.
            # Though this might fail for filesystems without support, like NFS.
            _renameat2(src_split[0], src_split[1], dst_split[0], dst_split[1], flags)
            return
        except OSError as e:
            # ENOSYS: kernel or libc does not support renameat2
            # EINVAL / ENOTSUP: filesystem does not support the flags (e.g. NFS)
            if e.errno in (errno.ENOSYS, errno.EINVAL, errno.ENOTSUP):
                _renameat2_fallback(src, dest, flags)
                return
            raise


def exchange(src: os.PathLike, dest: os.PathLike) -> None:
    """Atomically exchange paths between two files."""
    renameat2(src, dest, Renameat2.RENAME_EXCHANGE)
