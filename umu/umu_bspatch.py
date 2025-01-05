import os
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from enum import Enum
from mmap import ACCESS_READ, ACCESS_WRITE, MADV_DONTNEED, mmap
from pathlib import Path
from shutil import rmtree
from typing import TypedDict

from umu.umu_log import log
from umu.umu_util import memfdfile

with suppress(ModuleNotFoundError):
    from pyzstd import DParameter, ZstdDict, decompress
    from xxhash import xxh3_64_intdigest


class FileType(Enum):
    """Represents an file type."""

    # File types currently supported by mtree(1)
    File = "file"
    Block = "block"
    Char = "char"
    Dir = "dir"
    Fifo = "fifo"
    Link = "link"
    Socket = "socket"


class Entry(TypedDict):
    """Represents an entry within a patch section of a patch file."""

    # Binary delta data, compressed data or symbolic link's target
    data: bytes
    # File mode bits as decimal
    mode: int
    # File's name as a relative path with the base name ommitted
    # e.g., protonfixes/gamefixes-umu/umu-zenlesszonezero.py
    name: str
    # File's type
    type: FileType
    # xxhash result after applying the binary patch
    xxhash: int
    # File's modification time
    time: float
    # File's size
    size: int


class ManifestEntry(TypedDict):
    """Represents an entry within a manifest section of a patch file."""

    # File mode bits as decimal
    mode: int
    # File's name as a relative path with the base name omitted
    # e.g., protonfixes/gamefixes-umu/umu-zenlesszonezero.py
    name: str
    # xxhash result
    xxhash: int
    # File size
    size: int
    # File modification time
    time: float


class Content(TypedDict):
    """Represent a child of the root section, containing patch sections of a patch file."""

    manifest: list[ManifestEntry]
    # List of binaries to add in target directory
    add: list[Entry]
    # List of binaries to update in target directory
    update: list[Entry]
    # List of binaries to delete in target directory
    delete: list[Entry]
    source: str
    target: str


class ContentContainer(TypedDict):
    """Represent the root section of a patch file."""

    contents: list[Content]
    # Ed25519 digital signature of 'contents'
    signature: tuple[bytes, bytes]
    # Ed25519 SSH public key
    public_key: tuple[bytes, bytes]


MMAP_MIN = 16 * 1024

ZSTD_WINDOW_LOG_MIN = 10


class CustomPatcher:
    """Class for updating the contents within a compatibility tool directory.

    Intended to update supported tools like Proton and the Steam Linux Runtime within
    $XDG_DATA_HOME/umu.

    Given a patch file and two directories, 'a' and 'b', that have similar structure
    and where 'a' is already present on the system, will update all the contents within
    'a' to recreate 'b'. The patch file format will drive behavior and will contain all
    the necessary data and metadata to create 'b'.
    """

    def __init__(  # noqa: D107
        self,
        content: Content,
        compat_tool: Path,
        thread_pool: ThreadPoolExecutor,
    ) -> None:
        self._arc_contents: Content = content
        self._arc_manifest: list[ManifestEntry] = self._arc_contents["manifest"]
        self._compat_tool = compat_tool
        self._thread_pool = thread_pool
        self._futures: list[Future] = []

    def add_binaries(self) -> None:
        """Add binaries within a compatibility tool.

        Handles the case where the subdirectory contents in 'b' are not in 'a'.

        Will only operate on files, links and directories. Files will be recreated by
        decompressing the data in the patch item. Links will be symlinked to its target
        and directories will be created.
        """
        # Create new files, if there are any items
        for item in self._arc_contents["add"]:
            build_file: Path = self._compat_tool.joinpath(item["name"])
            if item["type"] == FileType.File.value:
                # Decompress the zstd data and write the file
                self._futures.append(
                    self._thread_pool.submit(self._write_proton_file, build_file, item)
                )
                continue
            if item["type"] == FileType.Link.value:
                build_file.symlink_to(item["data"])
                continue
            if item["type"] == FileType.Dir.value:
                build_file.mkdir(mode=item["mode"], exist_ok=True, parents=True)
                continue
            log.warning(
                "Found file '%s' with type '%s', skipping its inclusion",
                item["name"],
                item["type"],
            )

    def update_binaries(self) -> None:
        """Update binaries within a compatibility tool.

        Handles the case where the subdirectory contents between 'a' and 'b' differ,
        where 'b' is the new version.

        Will apply a binary patch for files that need to be updated. Directories will
        have its permissions changed. Links will be deleted.
        """
        for item in self._arc_contents["update"]:
            build_file: Path = self._compat_tool.joinpath(item["name"])
            if item["type"] == FileType.File.value:
                # For files, apply a binary patch
                self._futures.append(
                    self._thread_pool.submit(self._patch_proton_file, build_file, item)
                )
                continue
            if item["type"] == FileType.Dir.value:
                # For directories, change permissions
                os.chmod(build_file, item["mode"], follow_symlinks=False)  # noqa: PTH101
                continue
            if item["type"] == FileType.Link.value:
                # For links, replace the links
                build_file.unlink()
                build_file.symlink_to(item["data"])
                continue
            log.warning(
                "Found file '%s' with type '%s', skipping its update",
                item["name"],
                item["type"],
            )

    def delete_binaries(self) -> None:
        """Delete obsolete binaries within a compatibility tool.

        Handles the case where the subdirectory contents of 'a' are not in 'b',
        where 'b' is the new version.

        Will only operate on links, normal files, and directories while skipping
        everything else.
        """
        for item in self._arc_contents["delete"]:
            if (
                item["type"] == FileType.File.value
                or item["type"] == FileType.Link.value
            ):
                self._compat_tool.joinpath(item["name"]).unlink(missing_ok=True)
                continue
            if item["type"] == FileType.Dir.value:
                self._thread_pool.submit(
                    rmtree, str(self._compat_tool.joinpath(item["name"]))
                )
                continue
            log.warning(
                "Found file '%s' with type '%s', skipping its update",
                item["name"],
                item["type"],
            )

    def verify_integrity(self) -> None:
        """Verify the expected mode, size, file and digest of the compatibility tool."""
        for item in self._arc_manifest:
            self._futures.append(
                self._thread_pool.submit(self._check_binaries, self._compat_tool, item)
            )

    def result(self) -> list[Future]:
        """Return the currently submitted tasks."""
        return self._futures

    def _check_binaries(
        self, proton: Path, item: ManifestEntry
    ) -> ManifestEntry | None:
        rpath: Path = proton.joinpath(item["name"])

        try:
            with rpath.open("rb") as fp:
                stats: os.stat_result = os.fstat(fp.fileno())
                xxhash: int = 0
                if item["size"] != stats.st_size:
                    log.error(
                        "Expected size %s, received %s", item["size"], stats.st_size
                    )
                    return None
                if item["mode"] != stats.st_mode:
                    log.error(
                        "Expected mode %s, received %s", item["mode"], stats.st_mode
                    )
                    return None
                if stats.st_size > MMAP_MIN:
                    with mmap(fp.fileno(), length=0, access=ACCESS_READ) as mm:
                        # Ignore. Passing an mmap is valid here
                        # See https://docs.python.org/3/library/mmap.html#module-mmap
                        xxhash = xxh3_64_intdigest(mm)  # type: ignore
                        mm.madvise(MADV_DONTNEED, 0, stats.st_size)
                else:
                    xxhash = xxh3_64_intdigest(fp.read())
                if item["xxhash"] != xxhash:
                    log.error("Expected xxhash %s, received %s", item["xxhash"], xxhash)
                    return None
        except FileNotFoundError:
            log.debug("Aborting partial update, file not found: %s", rpath)
            return None

        return item

    def _patch_proton_file(self, path: Path, item: Entry) -> None:
        bdiff: bytes = item["data"]
        digest: int = item["xxhash"]
        mode: int = item["mode"]
        size: int = item["size"]

        try:
            # Since some wine binaries are missing the writable bit and
            # we're memory mapping files. Before applying a binary patch,
            # ensure the file is writable
            os.chmod(path, 0o700, follow_symlinks=False)  # noqa: PTH101

            # With our patch file, apply the delta in place
            with path.open("rb+") as fp:
                stats: os.stat_result = os.stat(fp.fileno())  # noqa: PTH116
                xxhash: int = 0

                # If less than the window log, write the data
                # The patcher inserts the raw, decompressed data in this case
                if max(stats.st_size, size).bit_length() < ZSTD_WINDOW_LOG_MIN:
                    fp.write(bdiff)
                    fp.truncate(size)
                    os.lseek(fp.fileno(), 0, os.SEEK_SET)

                    xxhash = xxh3_64_intdigest(fp.read())
                    if xxhash != digest:
                        err: str = (
                            f"Expected xxhash {digest}, received {xxhash} for file "
                            f"'{path}' truncating from size {stats.st_size} -> {size}"
                        )
                        raise ValueError(err)

                    os.fchmod(fp.fileno(), mode)
                    return

                # Apply our patch to the file in-place
                with mmap(fp.fileno(), length=0, access=ACCESS_WRITE) as mm:
                    # Prepare the zst dictionary and opt
                    zst_dict = ZstdDict(mm, is_raw=True)
                    zst_opt = {DParameter.windowLogMax: 31}

                    # If file will become large, increase
                    if stats.st_size < size:
                        mm.resize(size)

                    # Patch the region
                    mm[:size] = decompress(
                        bdiff, zstd_dict=zst_dict.as_prefix, option=zst_opt
                    )

                    # If file will become small, decrease
                    if size < stats.st_size:
                        mm.resize(size)

                    # Ignore. Passing an mmap is valid
                    xxhash = xxh3_64_intdigest(mm)  # type: ignore

                    if xxhash != digest:
                        err: str = (
                            f"Expected xxhash {digest}, received {xxhash} for "
                            f"file '{path}' truncating from size {stats.st_size} -> {size}"
                        )
                        raise ValueError(err)

                    mm.madvise(MADV_DONTNEED, 0, size)

                # Update the file's metadata
                os.fchmod(fp.fileno(), mode)
        except BaseException as e:
            log.exception(e)
            log.warning("File '%s' may be corrupt and has mode bits 0o700", path)
            raise

    def _write_proton_file(self, path: Path, item: Entry) -> None:
        data: bytes = item["data"]
        digest: int = item["xxhash"]
        mode: int = item["mode"]
        size: int = item["size"]

        with memfdfile(path.name) as fp:
            xxhash: int = 0

            fp.truncate(size)

            # Decompress our data and write to our file
            with mmap(fp.fileno(), length=0, access=ACCESS_WRITE) as mm:
                mm[:] = decompress(data)
                # Ignore. Passing an mmap is valid
                xxhash = xxh3_64_intdigest(mm)  # type: ignore

                if xxhash != digest:
                    err: str = (
                        f"Expected xxhash {digest}, received {xxhash} for fd "
                        f"{fp.fileno()} from source {path}"
                    )
                    raise ValueError(err)

                with path.open("wb") as file:
                    os.sendfile(file.fileno(), fp.fileno(), 0, size)
                    os.fchmod(file.fileno(), mode)

                mm.madvise(MADV_DONTNEED, 0, size)
