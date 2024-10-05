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

from pathlib import Path
from secrets import token_urlsafe
from shutil import move, rmtree
from subprocess import run
from tarfile import open as taropen
from tempfile import TemporaryDirectory, mkdtemp

from filelock import FileLock

from umu import __pressure_vessel_runtimes__
from umu.umu_consts import UMU_CACHE, UMU_LOCAL
from umu.umu_log import log
from umu.umu_util import (
    find_obsolete,
    get_vdf_value,
    https_connection,
    run_zenity,
)

try:
    from tarfile import tar_filter

    has_data_filter: bool = True
except ImportError:
    has_data_filter: bool = False


def _install_umu(
    local: Path,
    runtime_platform: tuple[str, str, str],
    thread_pool: ThreadPoolExecutor,
    client_session: HTTPSConnection,
) -> None:
    resp: HTTPResponse
    archive: str
    base_url: str
    tmp: Path = Path(mkdtemp())
    ret: int = 0  # Exit code from zenity
    token: str = f"?versions={token_urlsafe(16)}"

    # When using an existing obsolete proton build, download its intended
    # runtime. Handles cases where on a new install, the user or the client
    # passes and existing obsolete proton build but its corresponding runtime
    # has not been downloaded for them yet.
    if _is_obsolete_umu(runtime_platform):
        toolmanifest: Path = Path(os.environ["PROTONPATH"], "toolmanifest.vdf")
        compat_tool: str = get_vdf_value(
            toolmanifest,
            "require_tool_appid",
        )

        log.warning(
            "%s is obsolete, downloading obsolete steamrt",
            toolmanifest.parent.name,
        )

        # Change runtime paths and runtime base platform
        for pv_runtime in __pressure_vessel_runtimes__:
            if compat_tool in pv_runtime:
                log.debug(
                    "Changing SLR base platform: %s -> %s",
                    runtime_platform,
                    pv_runtime,
                )
                log.debug(
                    "Changing base directory: '%s' -> '%s'",
                    local,
                    local.parent / pv_runtime[0],
                )
                runtime_platform = pv_runtime
                local = local.parent / pv_runtime[0]
                break

    local.mkdir(parents=True, exist_ok=True)

    # Codename for the runtime (e.g., 'sniper')
    # Archive containing the runtime
    archive = f"SteamLinuxRuntime_{runtime_platform[1]}.tar.xz"
    base_url = (
        f"https://repo.steampowered.com/steamrt-images-{runtime_platform[1]}"
        "/snapshots/latest-container-runtime-public-beta"
    )

    log.debug("Codename: %s", runtime_platform[1])
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
            f"/steamrt-images-{runtime_platform[1]}"
            "/snapshots/latest-container-runtime-public-beta"
        )
        hashsum = sha256()

        # Get the digest for the runtime archive
        client_session.request("GET", f"{endpoint}/SHA256SUMS{token}")

        with client_session.getresponse() as resp:
            if resp.status != 200:
                err: str = (
                    f"repo.steampowered.com returned the status: {resp.status}"
                )
                raise HTTPException(err)

            # Parse SHA256SUMS
            for line in resp.read().decode("utf-8").splitlines():
                if line.endswith(archive):
                    digest = line.split(" ")[0]
                    break

        # Download the runtime
        log.console(
            f"Downloading latest steamrt {runtime_platform[1]}, please wait..."
        )
        client_session.request("GET", f"{endpoint}/{archive}{token}")

        with (
            client_session.getresponse() as resp,
            tmp.joinpath(archive).open(mode="ab+", buffering=0) as file,
        ):
            if resp.status != 200:
                err: str = (
                    f"repo.steampowered.com returned the status: {resp.status}"
                )
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

        with (
            taropen(f"{tmpcache}/{archive}", "r:xz") as tar,
        ):
            futures: list[Future] = []

            if has_data_filter:
                log.debug("Using filter for archive")
                tar.extraction_filter = tar_filter
            else:
                log.warning("Python: %s", sys.version)
                log.warning("Using no data filter for archive")
                log.warning("Archive will be extracted insecurely")

            # Extract the entirety of the archive w/ or w/o the data filter
            log.debug(
                "Extracting: %s -> %s", f"{tmpcache}/{archive}", tmpcache
            )
            tar.extractall(path=tmpcache)  # noqa: S202

            # Move the files to the correct location
            source_dir: Path = tmp.joinpath(
                f"SteamLinuxRuntime_{runtime_platform[1]}"
            )
            log.debug("Source: %s", source_dir)
            log.debug("Destination: %s", local)

            # Move each file to the dest dir, overwriting if exists
            futures.extend(
                [
                    thread_pool.submit(_move, file, source_dir, UMU_LOCAL)
                    for file in source_dir.glob("*")
                ]
            )

            # Remove the archive
            futures.append(thread_pool.submit(rmtree, str(tmpcache)))

            for future in futures:
                future.result()

    # Rename _v2-entry-point
    log.debug("Renaming: _v2-entry-point -> umu")
    UMU_LOCAL.joinpath("_v2-entry-point").rename(UMU_LOCAL.joinpath("umu"))

    # Validate the runtime after moving the files
    check_runtime(local, runtime_platform[1])


def setup_umu(
    root: Traversable,
    local: Path,
    runtime_platform: tuple[str, str, str],
    thread_pool: ThreadPoolExecutor,
) -> None:
    """Install or update the runtime for the current user."""
    log.debug("Root: %s", root)
    log.debug("Local: %s", local)
    log.debug("Steam Linux Runtime (latest): %s", runtime_platform[0])
    log.debug("Codename: %s", runtime_platform[1])
    log.debug("App ID: %s", runtime_platform[2])
    host: str = "repo.steampowered.com"

    # New install or umu dir is empty
    if not local.exists() or not any(local.iterdir()):
        log.debug("New install detected")
        log.console(
            "Setting up Unified Launcher for Windows Games on Linux..."
        )
        with https_connection(host) as client_session:
            _restore_umu(
                local / runtime_platform[0],
                runtime_platform,
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
        _update_umu(
            local / runtime_platform[0],
            runtime_platform,
            thread_pool,
            client_session,
        )


def _update_umu(
    local: Path,
    runtime_platform: tuple[str, str, str],
    thread_pool: ThreadPoolExecutor,
    client_session: HTTPSConnection,
) -> None:
    """For existing installations, check for updates to the runtime.

    The runtime platform will be updated to the latest public beta by comparing
    the local VERSIONS.txt against the remote one.
    """
    runtime: Path
    resp: HTTPResponse
    endpoint: str
    token: str = f"?version={token_urlsafe(16)}"

    log.debug("Existing install detected")
    log.debug("Sending request to '%s'...", client_session.host)

    # When using an existing obsolete proton build, skip its updates but allow
    # restoring it
    if _is_obsolete_umu(runtime_platform):
        toolmanifest: Path = Path(os.environ["PROTONPATH"], "toolmanifest.vdf")
        compat_tool: str = get_vdf_value(
            toolmanifest,
            "require_tool_appid",
        )

        # Change runtime paths and runtime base platform
        for pv_runtime in __pressure_vessel_runtimes__:
            if compat_tool in pv_runtime:
                log.debug(
                    "Changing SLR base platform: %s -> %s",
                    runtime_platform,
                    pv_runtime,
                )
                log.debug(
                    "Changing base directory: '%s' -> '%s'",
                    local,
                    local.parent / pv_runtime[0],
                )
                runtime_platform = pv_runtime
                local = local.parent / pv_runtime[0]
                break

    endpoint = (
        f"/steamrt-images-{runtime_platform[1]}"
        "/snapshots/latest-container-runtime-public-beta"
    )

    # Find the runtime directory (e.g., sniper_platform_0.20240530.90143)
    # Assume the directory begins with the alias
    try:
        runtime = max(
            file
            for file in local.glob(f"{runtime_platform[1]}*")
            if file.is_dir()
        )
    except ValueError:
        log.debug("*_platform_* directory missing in '%s'", local)
        log.warning("Runtime Platform not found")
        log.console("Restoring Runtime Platform...")
        _restore_umu(
            local,
            runtime_platform,
            thread_pool,
            lambda: len(
                [
                    file
                    for file in local.glob(f"{runtime_platform[1]}*")
                    if file.is_dir()
                ]
            )
            > 0,
            client_session,
        )
        return

    log.debug("Runtime: %s", runtime.name)

    if not local.joinpath("pressure-vessel").is_dir():
        log.debug("pressure-vessel directory missing in '%s'", local)
        log.warning("Runtime Platform not found")
        log.console("Restoring Runtime Platform...")
        _restore_umu(
            local,
            runtime_platform,
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
        versions: str = f"SteamLinuxRuntime_{runtime_platform[1]}.VERSIONS.txt"

        log.debug("VERSIONS.txt file missing in '%s'", local)

        # Restore the runtime if os-release is missing, otherwise pressure
        # vessel will crash when creating the variable directory
        if not release.is_file():
            log.debug("os-release file missing in '%s'", local)
            log.warning("Runtime Platform corrupt")
            log.console("Restoring Runtime Platform...")
            _restore_umu(
                local,
                runtime_platform,
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
                    build_id: str = (
                        line.removeprefix("BUILD_ID=").rstrip().strip('"')
                    )
                    url = (
                        f"/steamrt-images-{runtime_platform[1]}"
                        f"/snapshots/{build_id}"
                    )
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
                    local.joinpath("VERSIONS.txt").write_text(
                        resp.read().decode()
                    )

    # Skip SLR updates when not using the latest
    if _is_obsolete_umu(runtime_platform):
        log.warning(
            "%s is obsolete, skipping steamrt update",
            Path(os.environ["PROTONPATH"]).name,
        )
        return

    # Update the runtime if necessary by comparing VERSIONS.txt to the remote
    # repo.steampowered currently sits behind a Cloudflare proxy, which may
    # respond with cf-cache-status: HIT in the header for subsequent requests
    # indicating the response was found in the cache and was returned. Valve
    # has control over the CDN's cache control behavior, so we must not assume
    # all of the cache will be purged after new files are uploaded. Therefore,
    # always avoid the cache by appending a unique query to the URI
    url: str = (
        f"{endpoint}/SteamLinuxRuntime_{runtime_platform[1]}.VERSIONS.txt"
        f"{token}"
    )
    client_session.request("GET", url)

    # Attempt to compare the digests
    with client_session.getresponse() as resp:
        if resp.status != 200:
            log.warning(
                "repo.steampowered.com returned the status: %s", resp.status
            )
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
                _install_umu(
                    local, runtime_platform, thread_pool, client_session
                )
                log.debug("Removing: %s", runtime)
                rmtree(str(runtime))
                log.debug("Released file lock '%s'", lock.lock_file)

    log.console("steamrt is up to date")


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


def check_runtime(src: Path, codename: str) -> int:
    """Validate the file hierarchy of the runtime platform.

    The mtree file included in the Steam runtime platform will be used to
    validate the integrity of the runtime's metadata after its moved to the
    home directory and used to run games.
    """
    runtime: Path
    pv_verify: Path = src.joinpath("pressure-vessel", "bin", "pv-verify")
    ret: int = 1

    # Find the runtime directory
    try:
        runtime = max(
            file for file in src.glob(f"{codename}*") if file.is_dir()
        )
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

    return ret


def _restore_umu(
    local: Path,
    runtime_platform: tuple[str, str, str],
    thread_pool: ThreadPoolExecutor,
    callback_fn: Callable[[], bool],
    client_session: HTTPSConnection,
) -> None:
    with FileLock(f"{local.parent}/umu.lock") as lock:
        log.debug("Acquired file lock '%s'...", lock.lock_file)
        if callback_fn():
            log.debug("Released file lock '%s'", lock.lock_file)
            log.console("steamrt was restored")
            return
        _install_umu(local, runtime_platform, thread_pool, client_session)
        log.debug("Released file lock '%s'", lock.lock_file)


def _is_obsolete_umu(runtime_platform: tuple[str, str, str]) -> bool:
    return bool(
        os.environ.get("PROTONPATH")
        and os.environ.get("PROTONPATH") != "GE-Proton"
        and get_vdf_value(
            Path(os.environ["PROTONPATH"], "toolmanifest.vdf"),
            "require_tool_appid",
        )
        not in runtime_platform
    )
