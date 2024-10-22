import os
import sys
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha256
from http.client import HTTPException, HTTPResponse, HTTPSConnection

try:
    from importlib.resources.abc import Traversable
except ModuleNotFoundError:
    from importlib.abc import Traversable

from json import load
from pathlib import Path
from secrets import token_urlsafe
from shutil import move, rmtree
from subprocess import run
from tarfile import open as taropen
from tempfile import TemporaryDirectory, mkdtemp
from typing import Any

from filelock import FileLock

from umu.umu_consts import CONFIG, UMU_CACHE, UMU_LOCAL
from umu.umu_log import log
from umu.umu_util import find_obsolete, https_connection, run_zenity

try:
    from tarfile import tar_filter

    has_data_filter: bool = True
except ImportError:
    has_data_filter: bool = False


def create_shim(file_path: Path | None = None):
    """Create a shell script shim at the specified file path.

    This script sets the DISPLAY environment variable if certain conditions
    are met and executes the passed command.

    Args:
        file_path (Path, optional): The path where the shim script will be created.
            Defaults to UMU_LOCAL.joinpath("umu-shim").

    """
    # Set the default path if none is provided
    if file_path is None:
        file_path = UMU_LOCAL.joinpath("umu-shim")
    # Define the content of the shell script
    script_content = """#!/bin/sh

    if [ "${XDG_CURRENT_DESKTOP}" = "gamescope" ] || [ "${XDG_SESSION_DESKTOP}" = "gamescope" ]; then
        # Check if STEAM_MULTIPLE_XWAYLANDS is set to 1
        if [ "${STEAM_MULTIPLE_XWAYLANDS}" = "1" ]; then
            # Check if DISPLAY is set, if not, set it to ":1"
            if [ -z "${DISPLAY}" ]; then
                export DISPLAY=":1"
            fi
        fi
    fi

    # Execute the passed command
    "$@"

    # Capture the exit status
    status=$?
    echo "Command exited with status: $status"
    exit $status
    """

    # Write the script content to the specified file path
    with file_path.open('w') as file:
        file.write(script_content)

    # Make the script executable
    file_path.chmod(0o700)

def _install_umu(
    json: dict[str, Any],
    thread_pool: ThreadPoolExecutor,
    client_session: HTTPSConnection,
) -> None:
    resp: HTTPResponse
    tmp: Path = Path(mkdtemp())
    ret: int = 0  # Exit code from zenity
    # Codename for the runtime (e.g., 'sniper')
    codename: str = json["umu"]["versions"]["runtime_platform"]
    # Archive containing the runtime
    archive: str = f"SteamLinuxRuntime_{codename}.tar.xz"
    base_url: str = (
        f"https://repo.steampowered.com/steamrt-images-{codename}"
        "/snapshots/latest-container-runtime-public-beta"
    )
    token: str = f"?versions={token_urlsafe(16)}"

    log.debug("Codename: %s", codename)
    log.debug("URL: %s", base_url)

    # Download the runtime and optionally create a popup with zenity
    if os.environ.get("UMU_ZENITY") == "1":
        curl: str = "curl"
        opts: list[str] = [
            "-LJ",
            "--silent",
            "-O",
            f"{base_url}/{archive}",
            "--output-dir",
            str(tmp),
        ]
        msg: str = "Downloading umu runtime, please wait..."
        ret = run_zenity(curl, opts, msg)

    # Handle the exit code from zenity
    if ret:
        tmp.joinpath(archive).unlink(missing_ok=True)
        log.console("Retrying from Python...")

    if not os.environ.get("UMU_ZENITY") or ret:
        digest: str = ""
        endpoint: str = (
            f"/steamrt-images-{codename}"
            "/snapshots/latest-container-runtime-public-beta"
        )
        hashsum = sha256()

        # Get the digest for the runtime archive
        client_session.request("GET", f"{endpoint}/SHA256SUMS{token}")

        with client_session.getresponse() as resp:
            if resp.status != 200:
                err: str = f"repo.steampowered.com returned the status: {resp.status}"
                raise HTTPException(err)

            # Parse SHA256SUMS
            for line in resp.read().decode("utf-8").splitlines():
                if line.endswith(archive):
                    digest = line.split(" ")[0]
                    break

        # Download the runtime
        log.console(f"Downloading latest steamrt {codename}, please wait...")
        client_session.request("GET", f"{endpoint}/{archive}{token}")

        with (
            client_session.getresponse() as resp,
            tmp.joinpath(archive).open(mode="ab+", buffering=0) as file,
        ):
            if resp.status != 200:
                err: str = f"repo.steampowered.com returned the status: {resp.status}"
                raise HTTPException(err)

            chunk_size: int = 64 * 1024  # 64 KB
            buffer: bytearray = bytearray(chunk_size)
            view: memoryview = memoryview(buffer)
            while size := resp.readinto(buffer):
                file.write(view[:size])
                hashsum.update(view[:size])

            # Verify the runtime digest
            if hashsum.hexdigest() != digest:
                err: str = f"Digest mismatched: {archive}"
                raise ValueError(err)

        log.console(f"{archive}: SHA256 is OK")

    # Open the tar file and move the files
    log.debug("Opening: %s", tmp.joinpath(archive))

    UMU_CACHE.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(dir=UMU_CACHE) as tmpcache:
        log.debug("Created: %s", tmpcache)
        log.debug("Moving: %s -> %s", tmp.joinpath(archive), tmpcache)
        move(tmp.joinpath(archive), tmpcache)

        with (taropen(f"{tmpcache}/{archive}", "r:xz") as tar,):
            futures: list[Future] = []

            if has_data_filter:
                log.debug("Using filter for archive")
                tar.extraction_filter = tar_filter
            else:
                log.warning("Python: %s", sys.version)
                log.warning("Using no data filter for archive")
                log.warning("Archive will be extracted insecurely")

            # Ensure the target directory exists
            UMU_LOCAL.mkdir(parents=True, exist_ok=True)

            # Extract the entirety of the archive w/ or w/o the data filter
            log.debug("Extracting: %s -> %s", f"{tmpcache}/{archive}", tmpcache)
            tar.extractall(path=tmpcache)  # noqa: S202

            # Move the files to the correct location
            source_dir: Path = Path(tmpcache, f"SteamLinuxRuntime_{codename}")
            var: Path = UMU_LOCAL.joinpath("var")
            log.debug("Source: %s", source_dir)
            log.debug("Destination: %s", UMU_LOCAL)

            # Move each file to the dest dir, overwriting if exists
            futures.extend(
                [
                    thread_pool.submit(_move, file, source_dir, UMU_LOCAL)
                    for file in source_dir.glob("*")
                ]
            )

            if var.is_dir():
                log.debug("Removing: %s", var)
                # Remove the variable directory to avoid Steam Linux Runtime
                # related errors when creating it. Supposedly, it only happens
                # when going from umu-launcher 0.1-RC4 -> 1.1.1+
                # See https://github.com/Open-Wine-Components/umu-launcher/issues/213#issue-2576708738
                thread_pool.submit(rmtree, str(var))

            for future in futures:
                future.result()

    # Rename _v2-entry-point
    log.debug("Renaming: _v2-entry-point -> umu")
    UMU_LOCAL.joinpath("_v2-entry-point").rename(UMU_LOCAL.joinpath("umu"))
    create_shim()

    # Validate the runtime after moving the files
    check_runtime(UMU_LOCAL, json)


def setup_umu(root: Traversable, local: Path, thread_pool: ThreadPoolExecutor) -> None:
    """Install or update the runtime for the current user."""
    log.debug("Root: %s", root)
    log.debug("Local: %s", local)
    json: dict[str, Any] = _get_json(root, CONFIG)
    host: str = "repo.steampowered.com"

    # New install or umu dir is empty
    if not local.exists() or not any(local.iterdir()):
        log.debug("New install detected")
        log.console("Setting up Unified Launcher for Windows Games on Linux...")
        local.mkdir(parents=True, exist_ok=True)
        with https_connection(host) as client_session:
            _restore_umu(
                json,
                thread_pool,
                lambda: local.joinpath("umu").is_file(),
                client_session,
            )
        return

    if os.environ.get("UMU_RUNTIME_UPDATE") == "0":
        log.debug("Runtime Platform updates disabled")
        return

    find_obsolete()

    with https_connection(host) as client_session:
        _update_umu(local, json, thread_pool, client_session)


def _update_umu(
    local: Path,
    json: dict[str, Any],
    thread_pool: ThreadPoolExecutor,
    client_session: HTTPSConnection,
) -> None:
    """For existing installations, check for updates to the runtime.

    The runtime platform will be updated to the latest public beta by comparing
    the local VERSIONS.txt against the remote one.
    """
    runtime: Path
    resp: HTTPResponse
    codename: str = json["umu"]["versions"]["runtime_platform"]
    endpoint: str = (
        f"/steamrt-images-{codename}" "/snapshots/latest-container-runtime-public-beta"
    )
    token: str = f"?version={token_urlsafe(16)}"
    log.debug("Existing install detected")
    log.debug("Sending request to '%s'...", client_session.host)

    # Find the runtime directory (e.g., sniper_platform_0.20240530.90143)
    # Assume the directory begins with the alias
    try:
        runtime = max(file for file in local.glob(f"{codename}*") if file.is_dir())
    except ValueError:
        log.debug("*_platform_* directory missing in '%s'", local)
        log.warning("Runtime Platform not found")
        log.console("Restoring Runtime Platform...")
        _restore_umu(
            json,
            thread_pool,
            lambda: len([file for file in local.glob(f"{codename}*") if file.is_dir()])
            > 0,
            client_session,
        )
        return

    log.debug("Runtime: %s", runtime.name)
    log.debug("Codename: %s", codename)

    if not local.joinpath("pressure-vessel").is_dir():
        log.debug("pressure-vessel directory missing in '%s'", local)
        log.warning("Runtime Platform not found")
        log.console("Restoring Runtime Platform...")
        _restore_umu(
            json,
            thread_pool,
            lambda: local.joinpath("pressure-vessel").is_dir(),
            client_session,
        )
        return

    # Restore VERSIONS.txt
    # When the file is missing, the request for the image will need to be made
    # to the endpoint of the specific snapshot
    if not local.joinpath("VERSIONS.txt").is_file():
        url: str
        release: Path = runtime.joinpath("files", "lib", "os-release")
        versions: str = f"SteamLinuxRuntime_{codename}.VERSIONS.txt"

        log.debug("VERSIONS.txt file missing in '%s'", local)

        # Restore the runtime if os-release is missing, otherwise pressure
        # vessel will crash when creating the variable directory
        if not release.is_file():
            log.debug("os-release file missing in '%s'", local)
            log.warning("Runtime Platform corrupt")
            log.console("Restoring Runtime Platform...")
            _restore_umu(
                json,
                thread_pool,
                lambda: local.joinpath("VERSIONS.txt").is_file(),
                client_session,
            )
            return

        # Get the BUILD_ID value in os-release
        with release.open(mode="r", encoding="utf-8") as file:
            for line in file:
                if line.startswith("BUILD_ID"):
                    # Get the value after 'BUILD_ID=' and strip the quotes
                    build_id: str = line.removeprefix("BUILD_ID=").rstrip().strip('"')
                    url = f"/steamrt-images-{codename}" f"/snapshots/{build_id}"
                    break

        client_session.request("GET", f"{url}{token}")

        with client_session.getresponse() as resp:
            # Handle the redirect
            if resp.status == 301:
                location: str = resp.getheader("Location", "")
                log.debug("Location: %s", resp.getheader("Location"))
                # The stdlib requires reading the entire response body before
                # making another request
                resp.read()

                # Make a request to the new location
                client_session.request("GET", f"{location}/{versions}{token}")
                with client_session.getresponse() as resp_redirect:
                    if resp_redirect.status != 200:
                        log.warning(
                            "repo.steampowered.com returned the status: %s",
                            resp_redirect.status,
                        )
                        return
                    local.joinpath("VERSIONS.txt").write_text(resp.read().decode())

    # Update the runtime if necessary by comparing VERSIONS.txt to the remote
    # repo.steampowered currently sits behind a Cloudflare proxy, which may
    # respond with cf-cache-status: HIT in the header for subsequent requests
    # indicating the response was found in the cache and was returned. Valve
    # has control over the CDN's cache control behavior, so we must not assume
    # all of the cache will be purged after new files are uploaded. Therefore,
    # always avoid the cache by appending a unique query to the URI
    url: str = f"{endpoint}/SteamLinuxRuntime_{codename}.VERSIONS.txt{token}"
    client_session.request("GET", url)

    # Attempt to compare the digests
    with client_session.getresponse() as resp:
        if resp.status != 200:
            log.warning("repo.steampowered.com returned the status: %s", resp.status)
            return

        steamrt_latest_digest: bytes = sha256(resp.read()).digest()
        steamrt_local_digest: bytes = sha256(
            local.joinpath("VERSIONS.txt").read_bytes()
        ).digest()
        steamrt_versions: Path = local.joinpath("VERSIONS.txt")

        log.debug("Source: %s", url)
        log.debug("Digest: %s", steamrt_latest_digest)
        log.debug("Source: %s", steamrt_versions)
        log.debug("Digest: %s", steamrt_local_digest)

        if steamrt_latest_digest != steamrt_local_digest:
            lock: FileLock = FileLock(f"{local}/umu.lock")
            log.console("Updating steamrt to latest...")
            log.debug("Acquiring file lock '%s'...", lock.lock_file)

            with lock:
                log.debug("Acquired file lock '%s'", lock.lock_file)
                # Once another process acquires the lock, check if the latest
                # runtime has already been downloaded
                if (
                    steamrt_latest_digest
                    == sha256(steamrt_versions.read_bytes()).digest()
                ):
                    log.debug("Released file lock '%s'", lock.lock_file)
                    return
                _install_umu(json, thread_pool, client_session)
                log.debug("Removing: %s", runtime)
                rmtree(str(runtime))
                log.debug("Released file lock '%s'", lock.lock_file)

    # Restore shim
    if not local.joinpath("umu-shim").exists():
        create_shim()

    log.console("steamrt is up to date")


def _get_json(path: Traversable, config: str) -> dict[str, Any]:
    """Validate the state of the configuration file umu_version.json in a path.

    The configuration file will be used to update the runtime and it reflects
    the tools currently used by launcher. The key/value pairs umu and versions
    must exist.
    """
    json: dict[str, Any]
    # Steam Runtime platform values
    # See https://gitlab.steamos.cloud/steamrt/steamrt/-/wikis/home
    steamrts: set[str] = {
        "soldier",
        "sniper",
        "medic",
        "steamrt5",
    }

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
    if not json or "umu" not in json or "versions" not in json["umu"]:
        err: str = f"Failed to load {config} or 'umu' or 'versions' not in: {config}"
        raise ValueError(err)

    # The launcher will use the value runtime_platform to glob files. Attempt
    # to guard against directory removal attacks for non-system wide installs
    if json["umu"]["versions"]["runtime_platform"] not in steamrts:
        err: str = "Value for 'runtime_platform' is not a steamrt"
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
        rmtree(str(dest_file))

    if src.is_file() or src.is_dir():
        log.debug("Moving: %s -> %s", src_file, dest_file)
        move(src_file, dest_file)


def check_runtime(src: Path, json: dict[str, Any]) -> int:
    """Validate the file hierarchy of the runtime platform.

    The mtree file included in the Steam runtime platform will be used to
    validate the integrity of the runtime's metadata after its moved to the
    home directory and used to run games.
    """
    runtime: Path
    codename: str = json["umu"]["versions"]["runtime_platform"]
    pv_verify: Path = src.joinpath("pressure-vessel", "bin", "pv-verify")
    ret: int = 1

    # Find the runtime directory
    try:
        runtime = max(file for file in src.glob(f"{codename}*") if file.is_dir())
    except ValueError:
        log.warning("steamrt validation failed")
        log.warning("Could not find runtime in '%s'", src)
        return ret

    if not pv_verify.is_file():
        log.warning("steamrt validation failed")
        log.warning("File does not exist: '%s'", pv_verify)
        return ret

    log.console(f"Verifying integrity of {runtime.name}...")
    ret = run(
        [
            pv_verify,
            "--quiet",
            "--minimized-runtime",
            runtime.joinpath("files"),
        ],
        check=False,
    ).returncode

    if ret:
        log.warning("steamrt validation failed")
        log.debug("%s exited with the status code: %s", pv_verify.name, ret)
        return ret
    log.console(f"{runtime.name}: mtree is OK")

    if not UMU_LOCAL.joinpath("umu-shim").exists():
        create_shim()

    return ret


def _restore_umu(
    json: dict[str, Any],
    thread_pool: ThreadPoolExecutor,
    callback_fn: Callable[[], bool],
    client_session: HTTPSConnection,
) -> None:
    with FileLock(f"{UMU_LOCAL}/umu.lock") as lock:
        log.debug("Acquired file lock '%s'...", lock.lock_file)
        if callback_fn():
            log.debug("Released file lock '%s'", lock.lock_file)
            log.console("steamrt was restored")
            return
        _install_umu(json, thread_pool, client_session)
        log.debug("Released file lock '%s'", lock.lock_file)

    if not UMU_LOCAL.joinpath("umu-shim").exists():
        create_shim()
