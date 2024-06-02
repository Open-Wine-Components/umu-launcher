from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha256
from http.client import HTTPException, HTTPResponse, HTTPSConnection
from json import load
from os import environ
from pathlib import Path
from shutil import move, rmtree
from ssl import create_default_context
from subprocess import run
from sys import version
from tarfile import TarInfo
from tarfile import open as taropen
from tempfile import mkdtemp
from typing import Any

from umu_consts import CONFIG, UMU_LOCAL
from umu_log import log
from umu_util import run_zenity

CLIENT_SESSION: HTTPSConnection = HTTPSConnection(
    "repo.steampowered.com", context=create_default_context()
)

try:
    from tarfile import tar_filter
except ImportError:
    tar_filter: Callable[[str, str], TarInfo] = None


def _install_umu(
    json: dict[str, Any], thread_pool: ThreadPoolExecutor
) -> None:
    tmp: Path = Path(mkdtemp())
    # Exit code from zenity
    ret: int = 0
    # Archive containing the runtime
    archive: str = "SteamLinuxRuntime_sniper.tar.xz"
    codename: str = json["umu"]["versions"]["runtime_platform"]
    base_url: str = f"https://repo.steampowered.com/{codename}/images/latest-container-runtime-public-beta"
    # Value that corresponds to the runtime directory version
    build_id: str = ""

    log.debug("Codename: %s", codename)
    log.debug("URL: %s", base_url)

    # Download the runtime
    # Optionally create a popup with zenity
    if environ.get("UMU_ZENITY") == "1":
        bin: str = "curl"
        opts: list[str] = [
            "-LJ",
            "--silent",
            "--parallel",
            "-O",
            f"{base_url}/{archive}",
            "-O",
            f"{base_url}/BUILD_ID.txt",
            "--output-dir",
            tmp.as_posix(),
        ]
        msg: str = "Downloading umu runtime, please wait..."
        ret = run_zenity(bin, opts, msg)

    # Handle the exit code from zenity
    if ret:
        tmp.joinpath(archive).unlink(missing_ok=True)
        log.console("Retrying from Python...")

    if not environ.get("UMU_ZENITY") or ret:
        digest: str = ""
        endpoint: str = (
            f"/{codename}/images/latest-container-runtime-public-beta"
        )
        resp: HTTPResponse = None
        hash = sha256()

        # Get the version of the runtime
        CLIENT_SESSION.request("GET", f"{endpoint}/BUILD_ID.txt")
        resp = CLIENT_SESSION.getresponse()

        if resp.status != 200:
            err: str = (
                f"repo.steampowered.com returned the status: {resp.status}"
            )
            raise HTTPException(err)

        for line in resp.read().decode("utf-8").splitlines():
            build_id = line
            break

        # Get the digest for the runtime archive
        CLIENT_SESSION.request("GET", f"{endpoint}/SHA256SUMS")
        resp = CLIENT_SESSION.getresponse()

        if resp.status != 200:
            err: str = (
                f"repo.steampowered.com returned the status: {resp.status}"
            )
            raise HTTPException(err)

        for line in resp.read().decode("utf-8").splitlines():
            if line.endswith(archive):
                digest = line.split(" ")[0]
                break

        # Download the runtime
        CLIENT_SESSION.request("GET", f"{endpoint}/{archive}")
        resp = CLIENT_SESSION.getresponse()

        if resp.status != 200:
            err: str = (
                f"repo.steampowered.com returned the status: {resp.status}"
            )
            raise HTTPException(err)

        log.console(f"Downloading latest {codename}, please wait...")
        with tmp.joinpath(archive).open(mode="ab") as file:
            chunk_size: int = 64 * 1024  # 64 KB
            while True:
                chunk: bytes = resp.read(chunk_size)
                if not chunk:
                    break
                file.write(chunk)
                hash.update(chunk)

        # Verify the runtime digest
        if hash.hexdigest() != digest:
            err: str = f"Digests mismatched for {archive}"
            raise ValueError(err)

        log.console(f"{codename} {build_id}: SHA256 is OK")
        CLIENT_SESSION.close()

    # Open the tar file and move the files
    log.debug("Opening: %s", tmp.joinpath(archive))
    with (
        taropen(tmp.joinpath(archive), "r:xz") as tar,
    ):
        futures: list[Future] = []

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

        # Move each file to the destination directory, overwriting if it exists
        futures.extend(
            [
                thread_pool.submit(_move, file, source_dir, UMU_LOCAL)
                for file in source_dir.glob("*")
            ]
        )

        # Remove the archive
        futures.append(thread_pool.submit(tmp.joinpath(archive).unlink, True))

        for _ in futures:
            _.result()

        # Remove the extracted directory and all its contents
        log.debug("Removing: %s/SteamLinuxRuntime_sniper", tmp)
        if source_dir.exists():
            source_dir.rmdir()

        # Rename _v2-entry-point
        log.debug("Renaming: _v2-entry-point -> umu")
        UMU_LOCAL.joinpath("_v2-entry-point").rename(UMU_LOCAL.joinpath("umu"))

        # Write BUILD_ID.txt
        UMU_LOCAL.joinpath("BUILD_ID.txt").write_text(
            build_id
            or tmp.joinpath("BUILD_ID.txt").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        # Validate the runtime after moving the files
        check_runtime(
            UMU_LOCAL,
            json,
            build_id
            or tmp.joinpath("BUILD_ID.txt")
            .read_text(encoding="utf-8")
            .strip(),
        )


def setup_umu(
    root: Path, local: Path, thread_pool: ThreadPoolExecutor
) -> None:
    """Install or update the runtime for the current user."""
    json: dict[str, Any] = _get_json(root, CONFIG)
    log.debug("Root: %s", root)
    log.debug("Local: %s", local)

    # New install or umu dir is empty
    if not local.exists() or not any(local.iterdir()):
        log.debug("New install detected")
        log.console(
            "Setting up Unified Launcher for Windows Games on Linux..."
        )
        local.mkdir(parents=True, exist_ok=True)
        _install_umu(json, thread_pool)
        return

    _update_umu(local, json, thread_pool)
    return


def _update_umu(
    local: Path, json: dict[str, Any], thread_pool: ThreadPoolExecutor
) -> None:
    """For existing installations, check for updates to the runtime.

    The runtime platform will be updated to the latest public beta by comparing
    the local VERSIONS.txt against the remote one.
    """
    codename: str = json["umu"]["versions"]["runtime_platform"]
    # NOTE: If we ever build our custom runtime, this url will need to change
    # as well as the hard coded file paths below
    endpoint: str = f"/{codename}/images/latest-container-runtime-public-beta"
    runtime: Path = None
    build_id: str = ""
    resp: HTTPResponse = None
    log.debug("Existing install detected")

    # The BUILD_ID.txt is used to identify the runtime directory.
    # Restore if it is missing and do not crash if it does not exist remotely
    if not local.joinpath("BUILD_ID.txt").is_file():
        CLIENT_SESSION.request("GET", f"{endpoint}/BUILD_ID.txt")
        resp = CLIENT_SESSION.getresponse()
        if resp.status != 200:
            log.warning(
                "repo.steampowered.com returned the status: %s",
                resp.status,
            )
        else:
            build_id = resp.read().decode("utf-8").strip()
            local.joinpath("BUILD_ID.txt").write_text(build_id)

    # Find the runtime directory
    if local.joinpath("BUILD_ID.txt").is_file():
        build_id = (
            build_id
            or local.joinpath("BUILD_ID.txt")
            .read_text(encoding="utf-8")
            .strip()
        )
        for file in local.glob(f"*{build_id}"):
            runtime = file
            break

    if (
        not runtime
        or not runtime.is_dir()
        or not local.joinpath("pressure-vessel").is_dir()
    ):
        log.warning("Runtime Platform not found")
        log.console("Restoring Runtime Platform...")
        _install_umu(json, thread_pool)
        return

    # Restore VERSIONS.txt
    # NOTE: Change 'SteamLinuxRuntime_sniper.VERSIONS.txt' when the version
    # changes (e.g., steamrt4 -> SteamLinuxRuntime_medic.VERSIONS.txt)
    if not local.joinpath("VERSIONS.txt").is_file():
        endpoint_sniper: str = f"/{codename}/images/{build_id}"
        CLIENT_SESSION.request("GET", endpoint_sniper)
        resp = CLIENT_SESSION.getresponse()
        log.warning("VERSIONS.txt not found")
        log.console("Restoring VERSIONS.txt...")
        if resp.status != 200:
            log.warning(
                "repo.steampowered.com returned the status: %s",
                resp.status,
            )
        else:
            local.joinpath("VERSIONS.txt").write_text(
                resp.read().decode("utf-8")
            )

    # Update the runtime if necessary by comparing VERSIONS.txt to the remote
    CLIENT_SESSION.request(
        "GET", f"{endpoint}/SteamLinuxRuntime_sniper.VERSIONS.txt"
    )
    resp = CLIENT_SESSION.getresponse()

    if resp.status != 200:
        log.warning(
            "repo.steampowered.com returned the status: %s", resp.status
        )
        CLIENT_SESSION.close()
        return

    if (
        sha256(resp.read()).digest()
        != sha256(local.joinpath("VERSIONS.txt").read_bytes()).digest()
    ):
        log.console(f"Updating {codename} to latest...")
        _install_umu(json, thread_pool)
        return
    log.console(f"{codename} is up to date")

    CLIENT_SESSION.close()


def _get_json(path: Path, config: str) -> dict[str, Any]:
    """Validate the state of the configuration file umu_version.json in a path.

    The configuration file will be used to update the runtime and it reflects
    the tools currently used by launcher. The key/value pairs umu and versions
    must exist.
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
            f"Failed to load {config} or 'umu' or 'versions' not in: {config}"
        )
        raise ValueError(err)

    return json


def _move(file: Path, src: Path, dst: Path) -> None:
    """Move a file or directory to a destination.

    In order for the source and destination directory to be identical, when
    moving a directory, the contents of that same directory at the destination
    will be removed.
    """
    src_file: Path = src.joinpath(file.name)
    dest_file: Path = dst.joinpath(file.name)

    if dest_file.is_dir():
        log.debug("Removing directory: %s", dest_file)
        rmtree(dest_file.as_posix())

    if src.is_file() or src.is_dir():
        log.debug("Moving: %s -> %s", src_file, dest_file)
        move(src_file, dest_file)


def check_runtime(src: Path, json: dict[str, Any], build_id: str) -> int:
    """Validate the file hierarchy of the runtime platform.

    The mtree file included in the Steam runtime platform will be used to
    validate the integrity of the runtime's metadata after its moved to the
    home directory and used to run games.
    """
    runtime_platform_value: str = json["umu"]["versions"]["runtime_platform"]
    pv_verify: Path = src.joinpath("pressure-vessel", "bin", "pv-verify")
    ret: int = 1
    runtime: Path = None

    if not build_id:
        log.warning("%s: runtime validation failed", runtime_platform_value)
        return ret

    # Find the runtime directory by its build id
    for file in src.glob(f"*{build_id}"):
        runtime = file
        break

    if not runtime or not runtime.is_dir():
        log.warning("%s: runtime validation failed", runtime_platform_value)
        log.warning("Could not find runtime in: %s", src)
        return ret

    if not pv_verify.is_file():
        log.warning("%s: runtime validation failed", runtime_platform_value)
        log.warning("File does not exist: %s", pv_verify)
        return ret

    log.console(
        f"Verifying integrity of {runtime_platform_value} {build_id}..."
    )
    ret = run(
        [
            pv_verify.as_posix(),
            "--quiet",
            "--minimized-runtime",
            runtime.joinpath("files").as_posix(),
        ],
        check=False,
    ).returncode

    if ret:
        log.warning("%s: runtime validation failed", runtime_platform_value)
        log.debug("pv-verify exited with the status code: %s", ret)
        return ret
    log.console(f"{runtime_platform_value} {build_id}: mtree is OK")

    return ret
