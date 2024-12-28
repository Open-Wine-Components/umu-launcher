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


class FileType(Enum):  # noqa: D101
    # All file types currently supported under mtree
    # See mtree(1)
    File = "file"
    Block = "block"
    Char = "char"
    Dir = "dir"
    Fifo = "fifo"
    Link = "link"
    Socket = "socket"


class Entry(TypedDict):  # noqa: D101
    # BSDIFF data, zstd compressed data or symbolic link's target
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


class ManifestEntry(TypedDict):  # noqa: D101
    # File mode bits as decimal
    mode: int
    # File's name as a relative path with the base name of the ommitted
    # e.g., protonfixes/gamefixes-umu/umu-zenlesszonezero.py
    name: str
    # xxhash result
    xxhash: int
    # File size
    size: int
    # File modification time
    time: float


class Content(TypedDict):  # noqa: D101
    manifest: list[ManifestEntry]
    # List of binaries to add in target directory
    add: list[Entry]
    # List of binaries to update in target directory
    update: list[Entry]
    # List of binaries to delete in target directory
    delete: list[Entry]
    source: str
    target: str


class ContentContainer(TypedDict):  # noqa: D101
    contents: list[Content]
    # Ed25519 digital signature of 'contents'
    signature: bytes
    # Ed25519 SSH public key
    public_key: str


MMAP_MIN = 16 * 1024

ZSTD_WINDOW_LOG_MIN = 10


class CustomPatcher:  # noqa: D101
    def __init__(  # noqa: D107
        self,
        content: Content,
        proton: Path,
        cache: Path,
        thread_pool: ThreadPoolExecutor,
    ) -> None:
        self._arc_contents: Content = content
        self._arc_manifest: list[ManifestEntry] = self._arc_contents[
            "manifest"
        ]
        self._proton = proton
        self._cache = cache
        self._thread_pool = thread_pool
        self._futures: list[Future] = []

    def add_binaries(self) -> None:  # noqa: D102
        # Create new files, if there are any items
        for item in self._arc_contents["add"]:
            build_file: Path = self._proton.joinpath(item["name"])
            if item["type"] == FileType.File.value:
                # Decompress the zstd data and write the file
                self._futures.append(
                    self._thread_pool.submit(
                        self._write_proton_file, build_file, item
                    )
                )
                continue
            if item["type"] == FileType.Link.value:
                build_file.symlink_to(item["data"])
                os.utime(
                    build_file,
                    (
                        build_file.stat(follow_symlinks=False).st_atime,
                        item["time"],
                    ),
                    follow_symlinks=False,
                )
                continue
            if item["type"] == FileType.Dir.value:
                build_file.mkdir(
                    mode=item["mode"], exist_ok=True, parents=True
                )
                os.utime(
                    build_file,
                    (
                        build_file.stat(follow_symlinks=False).st_atime,
                        item["time"],
                    ),
                    follow_symlinks=False,
                )
                continue
            log.warning(
                "Found file '%s' with type '%s', skipping its inclusion",
                item["name"],
                item["type"],
            )

    def update_binaries(self) -> None:  # noqa: D102
        for item in self._arc_contents["update"]:
            build_file: Path = self._proton.joinpath(item["name"])
            if item["type"] == FileType.File.value:
                # For files, apply a binary patch
                self._futures.append(
                    self._thread_pool.submit(
                        self._patch_proton_file, build_file, item
                    )
                )
                continue
            if item["type"] == FileType.Dir.value:
                # For directories, change permissions
                os.chmod(build_file, item["mode"], follow_symlinks=False)  # noqa: PTH101
                os.utime(
                    build_file,
                    (
                        build_file.stat(follow_symlinks=False).st_atime,
                        item["time"],
                    ),
                    follow_symlinks=False,
                )
                continue
            if item["type"] == FileType.Link.value:
                # For links, replace the links
                build_file.unlink()
                build_file.symlink_to(item["data"])
                os.utime(
                    build_file,
                    (
                        build_file.stat(follow_symlinks=False).st_atime,
                        item["time"],
                    ),
                    follow_symlinks=False,
                )
                continue
            log.warning(
                "Found file '%s' with type '%s', skipping its update",
                item["name"],
                item["type"],
            )

    def delete_binaries(self) -> None:  # noqa: D102
        # Delete files, if there are any items. Only operate on links, normal
        # files and directories while skipping everything else.
        for item in self._arc_contents["delete"]:
            if (
                item["type"] == FileType.File.value
                or item["type"] == FileType.Link.value
            ):
                self._proton.joinpath(item["name"]).unlink(missing_ok=True)
                continue
            if item["type"] == FileType.Dir.value:
                self._thread_pool.submit(
                    rmtree, str(self._proton.joinpath(item["name"]))
                )
                continue
            log.warning(
                "Found file '%s' with type '%s', skipping its update",
                item["name"],
                item["type"],
            )

    def verify_integrity(self) -> None:  # noqa: D102
        for item in self._arc_manifest:
            self._futures.append(
                self._thread_pool.submit(
                    self._check_proton_binaries, self._proton, item
                )
            )

    def result(self) -> list[Future]:  # noqa: D102
        return self._futures

    def _check_proton_binaries(
        self, proton: Path, item: ManifestEntry
    ) -> ManifestEntry | None:
        rpath: Path = proton.joinpath(item["name"])

        try:
            with rpath.open("rb") as fp:
                stats: os.stat_result = os.fstat(fp.fileno())
                xxhash: int = 0

                if item["size"] != stats.st_size:
                    return None

                if item["mode"] != stats.st_mode:
                    return None

                if item["time"] != stats.st_mtime:
                    return None

                if stats.st_size > MMAP_MIN:
                    with mmap(fp.fileno(), length=0, access=ACCESS_READ) as mm:
                        xxhash = xxh3_64_intdigest(mm)
                        mm.madvise(MADV_DONTNEED, 0, stats.st_size)
                else:
                    xxhash = xxh3_64_intdigest(fp.read())

                if item["xxhash"] != xxhash:
                    return None
        except FileNotFoundError:
            log.debug("Aborting partial update, file not found: %s", rpath)
            return None

        return item

    def _patch_proton_file(self, path: Path, item: Entry) -> None:
        bdiff: bytes = item["data"]
        digest: int = item["xxhash"]
        mode: int = item["mode"]
        time: float = item["time"]
        size: int = item["size"]

        try:
            # Since some wine binaries are missing the writable bit and
            # we're memory mapping files, before applying a binary patch,
            # ensure the file is writable
            os.chmod(path, 0o700, follow_symlinks=False)  # noqa: PTH101

            # With our patch file, apply the delta in place
            with path.open("rb+") as fp:
                stats: os.stat_result = os.stat(fp.fileno())  # noqa: PTH116
                xxhash: int = 0

                if stats.st_size < size:
                    fp.truncate(size)

                if max(stats.st_size, size).bit_length() < ZSTD_WINDOW_LOG_MIN:
                    fp.write(bdiff)
                    fp.truncate(size)
                    os.lseek(fp.fileno(), 0, os.SEEK_SET)

                    # Verify our data
                    xxhash = xxh3_64_intdigest(fp.read())
                    if xxhash != digest:
                        err: str = f"Expected xxhash {digest}, received {xxhash} for file '{path}' truncating from size {stats.st_size} -> {size}"
                        raise ValueError(err)

                    os.fchmod(fp.fileno(), mode)
                    os.utime(fp.fileno(), (stats.st_atime, time))
                    return

                # Apply our patch to the file in-place
                with mmap(fp.fileno(), length=0, access=ACCESS_WRITE) as mm:
                    # Patch the region
                    zst_dict = ZstdDict(mm[: stats.st_size], is_raw=True)
                    zst_opt = {DParameter.windowLogMax: 31}
                    mm[:size] = decompress(
                        bdiff, zstd_dict=zst_dict.as_prefix, option=zst_opt
                    )

                    # If file will become small, resize our map
                    if size < stats.st_size:
                        mm.resize(size)

                    # Compute our expected digest
                    xxhash = xxh3_64_intdigest(mm)

                    # Verify our data
                    if xxhash != digest:
                        err: str = f"Expected xxhash {digest}, received {xxhash} for file '{path}' truncating from size {stats.st_size} -> {size}"
                        raise ValueError(err)

                    mm.madvise(MADV_DONTNEED, 0, len(mm))

                # Update the file's metadata
                os.fchmod(fp.fileno(), mode)
                os.utime(fp.fileno(), (stats.st_atime, time))
        except ValueError:
            raise
        except (KeyboardInterrupt, OSError) as e:
            log.exception(e)
            log.error("Binary patch errored for file '%s'", path)
            log.warning(
                "File '%s' may be corrupt and has mode bits 0o700", path
            )
            raise

    def _write_proton_file(self, path: Path, item: Entry) -> None:
        data: bytes = item["data"]
        digest: int = item["xxhash"]
        mode: int = item["mode"]
        time: float = item["time"]
        size: int = item["size"]

        with memfdfile(path.name) as fp:
            xxhash: int = 0

            fp.truncate(size)

            with mmap(fp.fileno(), length=0, access=ACCESS_WRITE) as mm:
                # Decompress our data and write to our file.
                mm[:] = decompress(data)
                xxhash = xxh3_64_intdigest(mm)

                if xxhash != digest:
                    err: str = f"Expected xxhash {digest}, received {xxhash} for fd {fp.fileno()} from source {path}"
                    raise ValueError(err)

                os.lseek(fp.fileno(), 0, os.SEEK_CUR)

                # Write to our file
                stats: os.stat_result = os.fstat(fp.fileno())
                with path.open("wb") as file:
                    os.sendfile(file.fileno(), fp.fileno(), 0, size)
                    os.fchmod(file.fileno(), mode)
                    os.utime(file.fileno(), (stats.st_atime, time))

                mm.madvise(MADV_DONTNEED, 0, size)
