import os
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import file_digest, sha256

try:
    from importlib.resources.abc import Traversable
except ModuleNotFoundError:
    from importlib.abc import Traversable

from http import HTTPMethod, HTTPStatus
from pathlib import Path
from secrets import token_urlsafe
from shutil import move, rmtree
from subprocess import run
from tempfile import TemporaryDirectory, mkdtemp

from filelock import FileLock
from urllib3.exceptions import HTTPError
from urllib3.exceptions import TimeoutError as TimeoutErrorUrllib3
from urllib3.poolmanager import PoolManager
from urllib3.response import BaseHTTPResponse

from umu.umu_consts import UMU_CACHE, UMU_LOCAL
from umu.umu_log import log
from umu.umu_util import (
    extract_tarfile,
    has_umu_setup,
    run_zenity,
    write_file_chunks,
)

Codename = str

Variant = str

RuntimeVersion = tuple[Codename, Variant]

SessionPools = tuple[ThreadPoolExecutor, PoolManager]


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
    script_content = (
        "#!/bin/sh\n"
        "\n"
        'if [ "${XDG_CURRENT_DESKTOP}" = "gamescope" ] || [ "${XDG_SESSION_DESKTOP}" = "gamescope" ]; then\n'
        "    # Check if STEAM_MULTIPLE_XWAYLANDS is set to 1\n"
        '    if [ "${STEAM_MULTIPLE_XWAYLANDS}" = "1" ]; then\n'
        '        # Check if DISPLAY is set, if not, set it to ":1"\n'
        '        if [ -z "${DISPLAY}" ]; then\n'
        '            export DISPLAY=":1"\n'
        "        fi\n"
        "    fi\n"
        "fi\n"
        "\n"
        "# Execute the passed command\n"
        '"$@"\n'
        "\n"
        "# Capture the exit status\n"
        "status=$?\n"
        'echo "Command exited with status: $status" >&2\n'
        "exit $status\n"
    )

    # Write the script content to the specified file path
    with file_path.open("w") as file:
        file.write(script_content)

    # Make the script executable
    file_path.chmod(0o700)


def _install_umu(
    runtime_ver: RuntimeVersion,
    session_pools: SessionPools,
) -> None:
    resp: BaseHTTPResponse
    tmp: Path = Path(mkdtemp())
    ret: int = 0  # Exit code from zenity
    thread_pool, http_pool = session_pools
    codename, variant = runtime_ver
    # Archive containing the runtime
    archive: str = f"SteamLinuxRuntime_{codename}.tar.xz"
    base_url: str = (
        f"https://repo.steampowered.com/steamrt-images-{codename}"
        "/snapshots/latest-container-runtime-public-beta"
    )
    token: str = f"?versions={token_urlsafe(16)}"
    host: str = "repo.steampowered.com"
    parts: Path = tmp.joinpath(f"{archive}.parts")
    log.debug("Using endpoint '%s' for requests", base_url)

    UMU_CACHE.mkdir(parents=True, exist_ok=True)

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
        log.info("Retrying from Python...")

    if not os.environ.get("UMU_ZENITY") or ret:
        digest: str = ""
        endpoint: str = (
            f"/steamrt-images-{codename}"
            "/snapshots/latest-container-runtime-public-beta"
        )
        hashsum = sha256()
        headers: dict[str, str] | None = None
        cached_parts: Path = UMU_CACHE.joinpath(parts.name)

        # Get the digest for the runtime archive
        resp = http_pool.request(
            HTTPMethod.GET, f"{host}{endpoint}/SHA256SUMS{token}"
        )
        if resp.status != HTTPStatus.OK:
            err: str = (
                f"{resp.getheader('Host')} returned the status: {resp.status}"
            )
            raise HTTPError(err)

        # Parse SHA256SUMS
        for line in resp.data.decode(encoding="utf-8").splitlines():
            if line.endswith(archive):
                digest = line.split(" ")[0]

        # Resume from our cached file, if we were interrupted previously
        if cached_parts.is_file():
            log.info("Found '%s' in cache, resuming...", cached_parts.name)
            headers = {"Range": f"bytes={cached_parts.stat().st_size}-"}
            parts = cached_parts
            # Rebuild our hashed progress
            with parts.open("rb") as fp:
                hashsum = file_digest(fp, hashsum.name)
        else:
            log.info("Downloading %s (latest), please wait...", variant)

        resp = http_pool.request(
            HTTPMethod.GET,
            f"{host}{endpoint}/{archive}{token}",
            preload_content=False,
            headers=headers,
        )

        # Bail out for unexpected status codes
        if resp.status not in {
            HTTPStatus.OK,
            HTTPStatus.PARTIAL_CONTENT,
            HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE,
        }:
            err: str = (
                f"{resp.getheader('Host')} returned the status: {resp.status}"
            )
            raise HTTPError(err)

        # Download the runtime
        if resp.status != HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE:
            try:
                log.debug("Writing: %s", parts)
                hashsum = write_file_chunks(parts, resp, hashsum)
            except TimeoutErrorUrllib3:
                log.error("Aborting steamrt install due to network error")
                log.info(
                    "Moving '%s' to cache for future resumption", parts.name
                )
                move(parts, UMU_CACHE)
                raise

        # Release conn to the pool
        resp.release_conn()

        log.debug("Digest: %s", digest)
        if hashsum.hexdigest() != digest:
            err: str = f"Digest mismatched: {archive}"
            # Remove our cached file because it had probably got corrupted
            # somehow since the last launch. Abort the update then continue
            # to launch using existing runtime
            cached_parts.unlink(missing_ok=True)
            raise ValueError(err)

        log.info("%s: SHA256 is OK", archive)

        # Remove the .parts suffix
        move(parts, parts.with_suffix(""))
        parts = parts.with_suffix("")

    # Open the tar file and move the files
    log.debug("Opening: %s", parts)

    with TemporaryDirectory(dir=UMU_CACHE) as tmpcache:
        futures: list[Future] = []
        var: Path = UMU_LOCAL.joinpath("var")
        log.debug("Created: %s", tmpcache)
        log.debug("Moving: %s -> %s", tmp.joinpath(archive), tmpcache)
        move(parts, tmpcache)

        # Ensure the target directory exists
        UMU_LOCAL.mkdir(parents=True, exist_ok=True)
        log.debug("Extracting: %s -> %s", f"{tmpcache}/{archive}", tmpcache)
        extract_tarfile(Path(tmpcache, archive), Path(tmpcache))

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
    check_runtime(UMU_LOCAL, runtime_ver)


def setup_umu(
    root: Traversable,
    local: Path,
    runtime_ver: RuntimeVersion,
    session_pools: SessionPools,
) -> None:
    """Install or update the runtime for the current user."""
    log.debug("Root: %s", root)
    log.debug("Local: %s", local)

    # New install or umu dir is empty
    if not has_umu_setup(local):
        log.debug("New install detected")
        log.info("Setting up Unified Launcher for Windows Games on Linux...")
        local.mkdir(parents=True, exist_ok=True)
        _restore_umu(
            local,
            runtime_ver,
            session_pools,
            lambda: local.joinpath("umu").is_file(),
        )
        log.info("Using %s (latest)", runtime_ver[1])
        return

    if os.environ.get("UMU_RUNTIME_UPDATE") == "0":
        log.info("%s updates disabled, skipping", runtime_ver[1])
        return

    _update_umu(local, runtime_ver, session_pools)


def _update_umu(
    local: Path,
    runtime_ver: RuntimeVersion,
    session_pools: SessionPools,
) -> None:
    """For existing installations, check for updates to the runtime.

    The runtime platform will be updated to the latest public beta by comparing
    the local VERSIONS.txt against the remote one.
    """
    runtime: Path
    resp: BaseHTTPResponse
    _, http_pool = session_pools
    codename, variant = runtime_ver
    endpoint: str = (
        f"/steamrt-images-{codename}"
        "/snapshots/latest-container-runtime-public-beta"
    )
    # Create a token and append it to the URL to avoid the Cloudflare cache
    # Avoids infinite updates to the runtime each launch
    # See https://github.com/Open-Wine-Components/umu-launcher/issues/188
    token: str = f"?version={token_urlsafe(16)}"
    host: str = "repo.steampowered.com"
    log.debug("Existing install detected")
    log.debug("Using container runtime '%s' aka '%s'", variant, codename)
    log.debug("Checking updates for '%s'...", variant)

    # Find the runtime directory (e.g., sniper_platform_0.20240530.90143)
    # Assume the directory begins with the variant
    try:
        runtime = max(
            file for file in local.glob(f"{codename}*") if file.is_dir()
        )
    except ValueError:
        log.critical("*_platform_* directory missing in '%s'", local)
        log.info("Restoring Runtime Platform...")
        _restore_umu(
            local,
            runtime_ver,
            session_pools,
            lambda: len(
                [file for file in local.glob(f"{codename}*") if file.is_dir()]
            )
            > 0,
        )
        return

    # Restore the runtime when pressure-vessel is missing
    if not local.joinpath("pressure-vessel").is_dir():
        log.critical("pressure-vessel directory missing in '%s'", local)
        log.info("Restoring Runtime Platform...")
        _restore_umu(
            local,
            runtime_ver,
            session_pools,
            lambda: local.joinpath("pressure-vessel").is_dir(),
        )
        return

    # Restore VERSIONS.txt
    # When the file is missing, the request for the image will need to be made
    # to the endpoint of the specific snapshot
    if not local.joinpath("VERSIONS.txt").is_file():
        log.critical("VERSIONS.txt file missing in '%s'", local)
        platformid: str | None = _restore_umu_platformid(
            runtime, runtime_ver, session_pools
        )
        if platformid is None:
            _restore_umu(
                local,
                runtime_ver,
                session_pools,
                lambda: local.joinpath("VERSIONS.txt").is_file(),
            )
            return
        local.joinpath("VERSIONS.txt").write_text(platformid)

    # Fetch the version file
    url: str = (
        f"{host}{endpoint}/SteamLinuxRuntime_{codename}.VERSIONS.txt{token}"
    )
    log.debug("Sending request to '%s' for 'VERSIONS.txt'...", url)
    resp = http_pool.request(HTTPMethod.GET, url)
    if resp.status != HTTPStatus.OK:
        log.error(
            "%s returned the status: %s", resp.getheader("Host"), resp.status
        )
        return

    # Update our runtime
    _update_umu_platform(local, runtime, runtime_ver, session_pools, resp)

    # Restore shim if missing
    if not local.joinpath("umu-shim").is_file():
        create_shim()

    log.info("%s is up to date", variant)


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


def check_runtime(src: Path, runtime_ver: RuntimeVersion) -> int:
    """Validate the file hierarchy of the runtime platform.

    The mtree file included in the Steam runtime platform will be used to
    validate the integrity of the runtime's metadata after its moved to the
    home directory and used to run games.
    """
    runtime: Path
    codename, variant = runtime_ver
    pv_verify: Path = src.joinpath("pressure-vessel", "bin", "pv-verify")
    ret: int = 1

    # Find the runtime directory
    try:
        runtime = max(
            file for file in src.glob(f"{codename}*") if file.is_dir()
        )
    except ValueError:
        log.critical("%s validation failed", variant)
        log.critical("Could not find *_platform_* in '%s'", src)
        return ret

    if not pv_verify.is_file():
        log.warning("%s validation failed", variant)
        log.warning("File does not exist: '%s'", pv_verify)
        return ret

    log.info("Verifying integrity of %s...", runtime.name)
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
        log.warning("%s validation failed", variant)
        log.debug("%s exited with the status code: %s", pv_verify.name, ret)
        return ret
    log.info("%s: mtree is OK", runtime.name)

    return ret


def _restore_umu(
    local: Path,
    runtime_ver: RuntimeVersion,
    session_pools: SessionPools,
    callback_fn: Callable[[], bool],
) -> None:
    with FileLock(f"{local}/umu.lock") as lock:
        log.debug("Acquired file lock '%s'...", lock.lock_file)
        if callback_fn():
            log.debug("Released file lock '%s'", lock.lock_file)
            log.info("%s was restored", runtime_ver[1])
            return
        _install_umu(runtime_ver, session_pools)
        log.debug("Released file lock '%s'", lock.lock_file)


def _restore_umu_platformid(
    runtime_base: Path,
    runtime_ver: RuntimeVersion,
    session_pools: SessionPools,
) -> None | str:
    url: str = ""
    _, http_pool = session_pools
    codename, _ = runtime_ver
    release: Path = runtime_base.joinpath("files", "lib", "os-release")
    versions: str = f"SteamLinuxRuntime_{codename}.VERSIONS.txt"
    host: str = "repo.steampowered.com"

    # Restore the runtime if os-release is missing, otherwise pressure
    # vessel will crash when creating the variable directory
    if not release.is_file():
        log.critical("os-release file missing in *_platform_*")
        log.critical("Runtime Platform corrupt")
        log.info("Restoring Runtime Platform...")
        return None

    # Get the BUILD_ID value in os-release so we can get VERSIONS.txt
    with release.open(mode="r", encoding="utf-8") as file:
        for line in file:
            if line.startswith("BUILD_ID"):
                # Get the value after 'BUILD_ID=' and strip the quotes
                build_id: str = (
                    line.removeprefix("BUILD_ID=").rstrip().strip('"')
                )
                url = f"/steamrt-images-{codename}" f"/snapshots/{build_id}"
                break

    if not url:
        log.critical("Failed to parse os-release for BUILD_ID in *_platform_*")
        log.critical("Runtime Platform corrupt")
        log.info("Restoring Runtime Platform...")
        return None

    # Make the request to the VERSIONS.txt endpoint. It's fine to hit the
    # cache for this endpoint, as it differs to the latest-beta endpoint
    resp = http_pool.request(HTTPMethod.GET, f"{host}{url}{versions}")
    if resp.status != HTTPStatus.OK:
        log.error(
            "%s returned the status: %s",
            resp.getheader("Host"),
            resp.status,
        )
        return None

    # False positive from mypy.
    return resp.data.decode(encoding="utf-8")  # type: ignore


def _update_umu_platform(
    local: Path,
    runtime: Path,
    runtime_ver: RuntimeVersion,
    session_pools: SessionPools,
    resp: BaseHTTPResponse,
) -> None:
    _, variant = runtime_ver
    latest: bytes = sha256(resp.data).digest()
    current: bytes = sha256(
        local.joinpath("VERSIONS.txt").read_bytes()
    ).digest()
    versions: Path = local.joinpath("VERSIONS.txt")
    lock: FileLock = FileLock(f"{local}/umu.lock")

    # Compare our version file to upstream's, updating if different
    if latest != current:
        log.info("Updating %s to latest...", variant)
        log.debug("Acquiring file lock '%s'...", lock.lock_file)
        with lock:
            log.debug("Acquired file lock '%s'", lock.lock_file)
            # Once another process acquires the lock, check if the latest
            # runtime has already been downloaded
            if latest == sha256(versions.read_bytes()).digest():
                log.debug("Released file lock '%s'", lock.lock_file)
                return
            _install_umu(runtime_ver, session_pools)
            log.debug("Removing: %s", runtime)
            rmtree(str(runtime))
            log.debug("Released file lock '%s'", lock.lock_file)
