from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha256
from http.client import HTTPException
from json import load
from os import environ
from pathlib import Path
from shutil import move, rmtree
from ssl import SSLContext, create_default_context
from subprocess import run
from sys import version
from tarfile import TarInfo
from tarfile import open as taropen
from tempfile import mkdtemp
from typing import Any
from urllib.request import urlopen

from umu_consts import CONFIG, UMU_LOCAL
from umu_log import log
from umu_util import run_zenity

SSL_DEFAULT_CONTEXT: SSLContext = create_default_context()

try:
    from tarfile import tar_filter
except ImportError:
    tar_filter: Callable[[str, str], TarInfo] = None


def setup_runtime(json: dict[str, Any]) -> None:  # noqa: D103
    tmp: Path = Path(mkdtemp())
    ret: int = 0  # Exit code from zenity
    archive: str = "SteamLinuxRuntime_sniper.tar.xz"  # Archive containing the runtime
    codename: str = json["umu"]["versions"]["runtime_platform"]
    base_url: str = f"https://repo.steampowered.com/{codename}/images/latest-container-runtime-public-beta"
    build_id: str = ""
    log.debug("Codename: %s", codename)
    log.debug("URL: %s", base_url)

    # Download the runtime
    # Optionally create a popup with zenity
    if environ.get("UMU_ZENITY") == "1":
        bin: str = "curl"
        opts: list[str] = [
            "-LJO",
            "--silent",
            f"{base_url}/{archive}",
            "--output-dir",
            tmp.as_posix(),
        ]
        msg: str = "Downloading UMU-Runtime..."
        ret = run_zenity(bin, opts, msg)

    # Handle the exit code from zenity
    if ret:
        tmp.joinpath(archive).unlink(missing_ok=True)
        log.console("Retrying from Python...")

    if not environ.get("UMU_ZENITY") or ret:
        digest: str = ""

        # Get the version of the runtime
        with urlopen(f"{base_url}/BUILD_ID.txt", context=SSL_DEFAULT_CONTEXT) as resp:  # noqa: S310
            if resp.status != 200:
                err: str = f"repo.steampowered.com returned the status: {resp.status}"
                raise HTTPException(err)
            for line in resp.read().decode("utf-8").splitlines():
                build_id = line
                break

        # Get the digest for the runtime archive
        with (
            urlopen(  # noqa: S310
                f"{base_url}/SHA256SUMS", context=SSL_DEFAULT_CONTEXT
            ) as resp,
        ):
            if resp.status != 200:
                err: str = f"repo.steampowered.com returned the status: {resp.status}"
                raise HTTPException(err)
            for line in resp.read().decode("utf-8").splitlines():
                if line.endswith(archive):
                    digest = line.split(" ")[0]
                    break

        # Download the runtime and verify its digest
        log.console(f"Downloading latest {codename}, please wait...")
        with (
            urlopen(  # noqa: S310
                f"{base_url}/{archive}", context=SSL_DEFAULT_CONTEXT
            ) as resp,
        ):
            data: bytes = b""
            if resp.status != 200:
                err: str = f"repo.steampowered.com returned the status: {resp.status}"
                raise HTTPException(err)
            log.debug("Writing: %s", tmp.joinpath(archive))
            data = resp.read()
            if sha256(data).hexdigest() != digest:
                err: str = f"Digests mismatched for {archive}"
                raise ValueError(err)
            log.console(f"{codename} {build_id}: SHA256 is OK")
            tmp.joinpath(archive).write_bytes(data)

    # Open the tar file and move the files
    log.debug("Opening: %s", tmp.joinpath(archive))
    with (
        taropen(tmp.joinpath(archive), "r:xz") as tar,
        ThreadPoolExecutor() as executor,
    ):
        if tar_filter:
            log.debug("Using filter for archive")
            tar.extraction_filter = tar_filter
        else:
            log.warning("Python: %s", version)
            log.warning("Using no data filter for archive")
            log.warning("Archive will be extracted insecurely")

        # Ensure the target directory exists
        UMU_LOCAL.mkdir(parents=True, exist_ok=True)

        log.debug("Extracting archive files -> %s", tmp)
        for member in tar.getmembers():
            if member.name.startswith("SteamLinuxRuntime_sniper/"):
                tar.extract(member, path=tmp)

        # Move the files to the correct location
        source_dir: Path = tmp.joinpath("SteamLinuxRuntime_sniper")
        log.debug("Source: %s", source_dir)
        log.debug("Destination: %s", UMU_LOCAL)

        # Validate the runtime before moving the files
        check_runtime(source_dir, json)

        # Move each file to the destination directory, overwriting if it exists
        futures: list[Future] = [
            executor.submit(_move, file, source_dir, UMU_LOCAL)
            for file in source_dir.glob("*")
        ]
        for _ in futures:
            _.result()

        # Remove the extracted directory and all its contents
        log.debug("Removing: %s/SteamLinuxRuntime_sniper", tmp)
        if tmp.joinpath("SteamLinuxRuntime_sniper").exists():
            rmtree(tmp.joinpath("SteamLinuxRuntime_sniper").as_posix())

        log.debug("Removing: %s", tmp.joinpath(archive))
        tmp.joinpath(archive).unlink(missing_ok=True)

        # Rename _v2-entry-point
        log.debug("Renaming: _v2-entry-point -> umu")
        UMU_LOCAL.joinpath("_v2-entry-point").rename(UMU_LOCAL.joinpath("umu"))

        # Write BUILD_ID.txt
        UMU_LOCAL.joinpath("BUILD_ID.txt").write_text(build_id, encoding="utf-8")


def setup_umu(root: Path, local: Path) -> None:
    """Install or update umu files for the current user.

    When launching umu for the first time, umu_version.json and a runtime
    platform will be downloaded for Proton

    The file umu_version.json defines all of the tools that umu will use and
    it will be persisted at ~/.local/share/umu, which will be used to update
    the runtime. The configuration file in that path will be updated at launch
    whenever there's a new release
    """
    log.debug("Root: %s", root)
    log.debug("Local: %s", local)
    json: dict[str, Any] = _get_json(root, CONFIG)

    # New install or umu dir is empty
    if not local.exists() or not any(local.iterdir()):
        return _install_umu(local, json)

    return _update_umu(local, json)


def _install_umu(local: Path, json: dict[str, Any]) -> None:
    """Prepare and download the runtime platform.

    The launcher files will remain in the system path defined at build time, except
    umu-launcher which will be installed in $PREFIX/share/steam/compatibilitytools.d
    """
    log.debug("New install detected")
    log.console("Setting up Unified Launcher for Windows Games on Linux...")
    local.mkdir(parents=True, exist_ok=True)
    setup_runtime(json)
def _get_json(path: Path, config: str) -> dict[str, Any]:
    """Validate the state of the configuration file umu_version.json in a path.

    The configuration file will be used to update the runtime and it reflects
    the tools currently used by launcher. The key/value pairs 'umu' and 'versions' must
    exist.
    """
    json: dict[str, Any] = None

    # umu_version.json in the system path should always exist
    if not path.joinpath(config).is_file():
        err: str = (
            f"File not found: {config}\n"
            "Please reinstall the package to recover configuration file"
        )
        raise FileNotFoundError(err)

    with path.joinpath(config).open(mode="r", encoding="utf-8") as file:
        json = load(file)

    # Raise an error if "umu" and "versions" doesn't exist
    if not json or not json.get("umu") or not json.get("umu").get("versions"):
        err: str = (
            f"Failed to load {config} or 'umu' or 'versions' not in: {config}\n"
            "Please reinstall the package"
        )
        raise ValueError(err)

    return json


def _move(file: Path, src: Path, dst: Path) -> None:
    """Move a file or directory to a destination.

    In order for the source and destination directory to be identical, when
    moving a directory, the contents of that same directory at the
    destination will be removed
    """
    src_file: Path = src.joinpath(file.name)
    dest_file: Path = dst.joinpath(file.name)

    if dest_file.is_dir():
        log.debug("Removing directory: %s", dest_file)
        rmtree(dest_file.as_posix())

    if src.is_file() or src.is_dir():
        log.debug("Moving: %s -> %s", src_file, dest_file)
        move(src_file, dest_file)


def check_runtime(src: Path, json: dict[str, Any]) -> int:
    """Validate the file hierarchy of the runtime platform.

    The mtree file included in the Steam runtime platform will be used to
    validate the integrity of the runtime's metadata before its moved to the
    home directory and used to run games

    Validation is intended to only be performed after verifying the integrity
    of the archive and its contents
    """
    runtime_platform_value: str = json["umu"]["versions"]["runtime_platform"]
    pv_verify: Path = src.joinpath("pressure-vessel", "bin", "pv-verify")
    ret: int = 1

    if not pv_verify.is_file():
        log.warning("%s: validation failed", runtime_platform_value)
        log.warning("pv-verify not in: %s", src)
        return ret

    log.console(f"Verifying integrity of {runtime_platform_value}...")
    ret = run([pv_verify.as_posix(), "--quiet"], check=False).returncode

    if pv_verify.is_file() and ret:
        log.warning("%s: validation failed", runtime_platform_value)
        log.debug("pv-verify exited with the status code: %s", ret)
        return ret
    log.console(f"{runtime_platform_value}: mtree is OK")

    return ret
