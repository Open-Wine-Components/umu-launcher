import os
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from enum import Enum
from pathlib import Path
from shutil import rmtree
from typing import TypedDict

from umu.umu_log import log
from umu.umu_util import memfdfile

with suppress(ModuleNotFoundError):
    from .umu_delta import (
        bspatch_rs,
        bz2_decompress_rs,
        crc32_mmap_rs,
        crc32_rs,
    )


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
    # BSDIFF data, bz2 compressed data or symbolic link's target
    data: bytes
    # File mode bits as decimal
    mode: int
    # File's name as a relative path with the base name ommitted
    # e.g., protonfixes/gamefixes-umu/umu-zenlesszonezero.py
    name: str
    # File's type
    type: FileType
    # CRC32 result after applying the binary patch
    cksum: int
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
    # CRC32 result
    cksum: int
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
                # Decompress the bz2 data and write the file
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
                cksum: int = 0
                if item["size"] != stats.st_size:
                    return None
                if item["mode"] != stats.st_mode:
                    return None
                if item["time"] != stats.st_mtime:
                    return None
                # Following blake3's heuristic, don't use mmap if < 16KB
                if stats.st_size > MMAP_MIN:
                    cksum = crc32_mmap_rs(fp.fileno())
                else:
                    cksum = crc32_rs(fp.fileno())
                if item["cksum"] != cksum:
                    return None
        except FileNotFoundError:
            log.debug("Aborting partial update, file not found: %s", rpath)
            return None

        return item

    def _patch_proton_file(self, path: Path, item: Entry) -> None:
        bdiff: bytes = item["data"]
        digest: int = item["cksum"]
        mode: int = item["mode"]
        time: float = item["time"]

        try:
            # Since some wine binaries are missing the writable bit and
            # we're memory mapping files, before applying a binary patch,
            # ensure the file is writable
            os.chmod(path, 0o700, follow_symlinks=False)  # noqa: PTH101
            # With our patch file, apply the delta in place
            with path.open("rb+") as fp:
                stats: os.stat_result
                cksum: int = 0

                # Apply the patch
                bspatch_rs(fp.fileno(), bdiff)

                # Compute our expected digest
                # Following blake3's heuristic, don't use mmap if < 16KB
                stats = os.fstat(fp.fileno())
                if stats.st_size > MMAP_MIN:
                    cksum = crc32_mmap_rs(fp.fileno())
                else:
                    cksum = crc32_rs(fp.fileno())

                # Verify our data
                if cksum != digest:
                    log.error(
                        "Expected cksum %s, received %s for file '%s'",
                        digest,
                        cksum,
                        path,
                    )
                    err: str = "Digest mismatch for binary patched result"
                    raise ValueError(err)

                # Update the file's metadata
                os.fchmod(fp.fileno(), mode)
                os.utime(
                    fp.fileno(),
                    (stats.st_atime, time),
                )
        except (ValueError, KeyboardInterrupt, OSError):
            log.error("Binary patch errored for file '%s'", path)
            log.warning("File '%s' has mode bits 0o700", path)
            raise

    def _write_proton_file(self, path: Path, item: Entry) -> None:
        data: bytes = item["data"]
        digest: int = item["cksum"]
        mode: int = item["mode"]
        time: float = item["time"]
        size: int = item["size"]

        with memfdfile(path.name) as fp:
            stats: os.stat_result
            cksum: int = 0

            # Decompress our data and write to our file.
            bz2_decompress_rs(data, fp.fileno(), size)

            # Following blake3's heuristic, don't use mmap if < 16KB
            stats = os.fstat(fp.fileno())
            if stats.st_size > MMAP_MIN:
                os.lseek(fp.fileno(), 0, os.SEEK_SET)
                cksum = crc32_mmap_rs(fp.fileno())
            else:
                os.lseek(fp.fileno(), 0, os.SEEK_SET)
                cksum = crc32_rs(fp.fileno())

            if cksum != digest:
                log.error(
                    "Expected %s, received %s for fd '%s' from source '%s'",
                    digest,
                    cksum,
                    fp.fileno(),
                    path,
                )
                err: str = "Digest mismatch when creating file"
                raise ValueError(err)

            # Write to our file
            with path.open("wb") as path_fp:
                os.sendfile(path_fp.fileno(), fp.fileno(), 0, stats.st_size)
                os.fchmod(path_fp.fileno(), mode)
                os.utime(path_fp.fileno(), (stats.st_atime, time))