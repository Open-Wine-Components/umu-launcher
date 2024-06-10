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
    "repo.steampowered.com",
    context=create_default_context(),
)

try:
    from tarfile import tar_filter
except ImportError:
    tar_filter: Callable[[str, str], TarInfo] = None


def _install_umu(
    json: dict[str, Any], thread_pool: ThreadPoolExecutor
) -> None:
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

    log.debug("Codename: %s", codename)
    log.debug("URL: %s", base_url)

    # Download the runtime and optionally create a popup with zenity
    if environ.get("UMU_ZENITY") == "1":
        bin: str = "curl"
        opts: list[str] = [
            "-LJ",
            "--silent",
            "-O",
            f"{base_url}/{archive}",
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
            f"/steamrt-images-{codename}"
            "/snapshots/latest-container-runtime-public-beta"
        )
        resp: HTTPResponse = None
        hash = sha256()

        # Get the digest for the runtime archive
        CLIENT_SESSION.request("GET", f"{endpoint}/SHA256SUMS")
        resp = CLIENT_SESSION.getresponse()

        if resp.status != 200:
            err: str = (
                f"repo.steampowered.com returned the status: {resp.status}"
            )
            CLIENT_SESSION.close()
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
            CLIENT_SESSION.close()
            raise HTTPException(err)

        log.console(
            f"Downloading latest steamrt {codename} (public beta),"
            "please wait..."
        )
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
            err: str = f"Digest mismatched: {archive}"
            CLIENT_SESSION.close()
            raise ValueError(err)

        log.console(f"steamrt {codename}: SHA256 is OK")
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

        # Extract the entirety of the archive w/ or w/o the data filter
        log.debug("Extracting archive files -> %s", tmp)
        tar.extractall(path=tmp)  # noqa: S202

        # Move the files to the correct location
        source_dir: Path = tmp.joinpath(f"SteamLinuxRuntime_{codename}")
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

        # Rename _v2-entry-point
        log.debug("Renaming: _v2-entry-point -> umu")
        UMU_LOCAL.joinpath("_v2-entry-point").rename(UMU_LOCAL.joinpath("umu"))

        # Validate the runtime after moving the files
        check_runtime(UMU_LOCAL, json)


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
    endpoint: str = (
        f"/steamrt-images-{codename}"
        "/snapshots/latest-container-runtime-public-beta"
    )
    runtime: Path = None
    resp: HTTPResponse = None
    log.debug("Existing install detected")

    # Find the runtime directory (e.g., sniper_platform_0.20240530.90143)
    # Assume the directory begins with the alias
    try:
        runtime = max(
            [file for file in local.glob(f"{codename}*") if file.is_dir()]
        )
    except ValueError:
        log.warning("Runtime Platform not found")
        log.console("Restoring Runtime Platform...")
        _install_umu(json, thread_pool)
        return
    log.debug("Runtime: %s", runtime.name)
    log.debug("Codename: %s", codename)

    if not local.joinpath("pressure-vessel").is_dir():
        log.warning("Runtime Platform not found")
        log.console("Restoring Runtime Platform...")
        _install_umu(json, thread_pool)
        return

    # Restore VERSIONS.txt
    # When the file is missing, the request for the image will need to be made
    # to the endpoint of the specific snapshot
    if not local.joinpath("VERSIONS.txt").is_file():
        release: Path = runtime.joinpath("files", "lib", "os-release")
        versions: str = f"SteamLinuxRuntime_{codename}.VERSIONS.txt"
        url: str = ""
        build_id: str = ""

        # Restore the runtime if os-release is missing, otherwise pressure
        # vessel will crash when creating the variable directory
        if not release.is_file():
            log.warning("Runtime Platform corrupt")
            log.console("Restoring Runtime Platform...")
            _install_umu(json, thread_pool)
            return

        # Get the BUILD_ID value in os-release
        with release.open(mode="r", encoding="utf-8") as file:
            for line in file:
                if line.startswith("BUILD_ID"):
                    _: str = line.strip()
                    # Get the value after '=' and strip the quotes
                    build_id = _[_.find("=") + 1 :].strip('"')
                    url = (
                        f"/steamrt-images-{codename}" f"/snapshots/{build_id}"
                    )
                    break

        CLIENT_SESSION.request("GET", url)
        resp = CLIENT_SESSION.getresponse()
        log.debug("Restoring VERSIONS.txt")

        # Handle the redirect
        if resp.status == 301:
            location: str = resp.getheader("Location")
            log.debug("Location: %s", resp.getheader("Location"))
            # The stdlib requires reading the entire response body before
            # making another request
            resp.read()
            CLIENT_SESSION.request("GET", f"{location}/{versions}")
            resp = CLIENT_SESSION.getresponse()

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
        "GET", f"{endpoint}/SteamLinuxRuntime_{codename}.VERSIONS.txt"
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
        log.debug("Removing: %s", runtime)
        rmtree(runtime.as_posix())
        return
    log.console("steamrt is up to date")

    CLIENT_SESSION.close()


def _get_json(path: Path, config: str) -> dict[str, Any]:
    """Validate the state of the configuration file umu_version.json in a path.

    The configuration file will be used to update the runtime and it reflects
    the tools currently used by launcher. The key/value pairs umu and versions
    must exist.
    """
    json: dict[str, Any] = None
    # Steam Runtime platform values
    # See https://gitlab.steamos.cloud/steamrt/steamrt/-/wikis/home
    steamrts: set[str] = {
        "scout",
        "heavy",
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
    if not json or not json.get("umu") or not json.get("umu").get("versions"):
        err: str = (
            f"Failed to load {config} or 'umu' or 'versions' not in: {config}"
        )
        raise ValueError(err)

    # The launcher will use the value runtime_platform to glob files. Attempt
    # to guard against directory removal attacks for non-system wide installs
    if json.get("umu").get("versions").get("runtime_platform") not in steamrts:
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
        rmtree(dest_file.as_posix())

    if src.is_file() or src.is_dir():
        log.debug("Moving: %s -> %s", src_file, dest_file)
        move(src_file, dest_file)


def check_runtime(src: Path, json: dict[str, Any]) -> int:
    """Validate the file hierarchy of the runtime platform.

    The mtree file included in the Steam runtime platform will be used to
    validate the integrity of the runtime's metadata after its moved to the
    home directory and used to run games.
    """
    codename: str = json["umu"]["versions"]["runtime_platform"]
    pv_verify: Path = src.joinpath("pressure-vessel", "bin", "pv-verify")
    ret: int = 1
    runtime: Path = None

    # Find the runtime directory
    try:
        runtime = max(
            [file for file in src.glob(f"{codename}*") if file.is_dir()]
        )
    except ValueError:
        log.warning("%s validation failed", codename)
        log.warning("Could not find runtime in '%s'", src)
        return ret

    if not pv_verify.is_file():
        log.warning("%s validation failed", codename)
        log.warning("File does not exist: '%s'", pv_verify)
        return ret

    log.console(f"Verifying integrity of steamrt {codename}...")
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
        log.warning("%s validation failed", codename)
        log.debug("%s exited with the status code: %s", pv_verify.name, ret)
        return ret
    log.console(f"steamrt {codename}: mtree is OK")

    return ret
