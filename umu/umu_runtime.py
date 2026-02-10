import os
import platform
import shlex
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from hashlib import sha256
from http import HTTPStatus
from pathlib import Path
from secrets import token_urlsafe
from shutil import move
from subprocess import run
from tempfile import TemporaryDirectory, mkdtemp

from urllib3.exceptions import HTTPError
from urllib3.poolmanager import PoolManager
from urllib3.response import BaseHTTPResponse

from umu import vdf
from umu.umu_consts import UMU_CACHE, UMU_LOCAL, FileLock, HTTPMethod
from umu.umu_log import log
from umu.umu_util import (
    exchange,
    extract_tarfile,
    file_digest,
    get_tempdir,
    has_umu_setup,
    run_zenity,
    unix_flock,
    write_file_chunks,
)

RuntimeVersion = tuple[str, str, str]

SessionPools = tuple[ThreadPoolExecutor, PoolManager]


def create_shim(file_path: Path):
    """Create a shell script shim at the specified file path.

    This script sets the DISPLAY environment variable if certain conditions
    are met and executes the passed command.

    Args:
        file_path (Path, optional): The path where the shim script will be created.

    """
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
        'exec "$@"\n'
    )
    file_path.write_text(script_content, encoding="utf-8")
    file_path.chmod(0o700)


def _install_umu(
    runtime_ver: RuntimeVersion,
    session_pools: SessionPools,
    local: Path,
) -> None:
    resp: BaseHTTPResponse
    UMU_CACHE.mkdir(parents=True, exist_ok=True)
    tmp: Path = get_tempdir()
    ret: int = 0  # Exit code from zenity
    thread_pool, http_pool = session_pools
    codename, variant, _ = runtime_ver
    base_url: str = f"https://repo.steampowered.com/{variant.removesuffix('-arm64')}/images/latest-public-beta/"
    token: str = f"?versions={token_urlsafe(16)}"
    host: str = "repo.steampowered.com"

    if codename.removeprefix("steamrt").removesuffix("-arm64").isdigit():
        archive = f"SteamLinuxRuntime_{codename.removeprefix('steamrt')}.tar.xz"
    else:
        archive = f"SteamLinuxRuntime_{codename}.tar.xz"
    parts = tmp.joinpath(f"{archive}.parts")

    log.debug("Using endpoint '%s' for requests", base_url)

    # Download the runtime and optionally create a popup with zenity
    if os.environ.get("UMU_ZENITY") == "1":
        curl: str = "curl"
        opts: list[str] = [
            "-LJ",
            "--silent",
            f"{base_url}/{archive}",
            "-o",
            str(parts),
        ]
        msg: str = "Downloading umu runtime, please wait..."
        ret = run_zenity(curl, opts, msg)
        parts = parts.rename(parts.parent / parts.name.removesuffix(".parts"))

    # Handle the exit code from zenity
    if ret:
        tmp.joinpath(archive).unlink(missing_ok=True)
        log.info("Retrying from Python...")

    if not os.environ.get("UMU_ZENITY") or ret:
        digest: str = ""
        buildid: str = ""
        endpoint: str = f"/{variant.removesuffix('-arm64')}/images/latest-public-beta"
        hashsum = sha256()
        headers: dict[str, str] | None = None
        cached_parts: Path

        # Get the digest for the runtime archive
        resp = http_pool.request(
            HTTPMethod.GET.value,
            f"{host}{endpoint}/SHA256SUMS{token}",
            preload_content=False,
        )
        if resp.status != HTTPStatus.OK:
            err: str = f"{resp.getheader('Host')} returned the status: {resp.status}"
            raise HTTPError(err)

        # Parse data for the archive digest
        target: bytes = archive.encode()
        while line := resp.readline():
            if line.rstrip().endswith(target):
                digest = line.split(b" ")[0].rstrip().decode()
                break

        resp.release_conn()

        # Get BUILD_ID.txt. We'll use the value to identify the file when cached.
        # This will guarantee we'll be picking up the correct file when resuming
        resp = http_pool.request(
            HTTPMethod.GET.value, f"{host}{endpoint}/BUILD_ID.txt{token}"
        )
        if resp.status != HTTPStatus.OK:
            err: str = f"{resp.getheader('Host')} returned the status: {resp.status}"
            raise HTTPError(err)

        buildid = resp.data.decode(encoding="utf-8").strip()
        log.debug("BUILD_ID: %s", buildid)

        # Extend our variables with the BUILD_ID
        log.debug("Renaming: %s -> %s", parts, parts.with_suffix(f".{buildid}.parts"))
        parts = parts.with_suffix(f".{buildid}.parts")
        cached_parts = UMU_CACHE.joinpath(f"{archive}.{buildid}.parts")

        # Resume from our cached file, if we were interrupted previously
        if cached_parts.is_file():
            log.info("Found '%s' in cache, resuming...", cached_parts.name)
            headers = {"Range": f"bytes={cached_parts.stat().st_size}-"}
            parts = cached_parts.rename(f"{mkdtemp(dir=UMU_CACHE)}/{parts.name}")
            # Rebuild our hashed progress
            with parts.open("rb") as fp:
                hashsum = file_digest(fp, hashsum.name)
        else:
            log.info("Downloading %s (latest), please wait...", variant)

        resp = http_pool.request(
            HTTPMethod.GET.value,
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
            err: str = f"{resp.getheader('Host')} returned the status: {resp.status}"
            raise HTTPError(err)

        # Download the runtime
        if resp.status != HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE:
            try:
                log.debug("Writing: %s", parts)
                hashsum = write_file_chunks(parts, resp, hashsum)
            except HTTPError:
                log.error("Aborting steamrt install due to network error")
                log.info("Moving '%s' to cache for future resumption", parts.name)
                move(parts, UMU_CACHE)
                raise

        # Release conn to the pool
        resp.release_conn()

        log.debug("Digest: %s", digest)
        if hashsum.hexdigest() != digest:
            # Remove our cached file because it had probably got corrupted
            # somehow since the last launch. Abort the update then continue
            # to launch using existing runtime
            cached_parts.unlink(missing_ok=True)
            err: str = (
                f"Digest mismatched: {archive}\n"
                "Possible reason: cached file corrupted or failed to acquire upstream digest\n"
                f"Link: {host}{endpoint}/{archive}"
            )
            raise ValueError(err)

        log.info("%s: SHA256 is OK", archive)

        # Remove the .parts and BUILD_ID suffix
        parts = parts.rename(
            parts.parent / parts.name.removesuffix(f".{buildid}.parts")
        )

    local.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=local.parent, prefix=".") as tempdir:
        log.debug("Created: %s", tempdir)
        log.debug("Moving: %s -> %s", parts, tempdir)
        move(parts, tempdir)

        extract_tarfile(Path(tempdir, archive), Path(tempdir))

        steamrt, *_ = archive.split(".tar.xz")
        log.debug("Exchanging: %s <-> %s", Path(tempdir, steamrt), local)
        exchange(Path(tempdir, steamrt), local)

        # Validate and post-install
        try:
            check_runtime(local, runtime_ver)
        finally:
            log.debug("Linking: umu -> _v2-entry-point")
            local.joinpath("umu").symlink_to("_v2-entry-point")


def setup_umu(
    local: Path, runtime_ver: RuntimeVersion, session_pools: SessionPools
) -> None:
    """Install or update the runtime for the current user."""
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

    The runtime platform will be updated to the latest public beta by
    confirming if the latest platform ID exists in the local VERSIONS.txt
    """
    resp: BaseHTTPResponse
    _, http_pool = session_pools
    codename, variant, _ = runtime_ver
    endpoint: str = f"/{variant.removesuffix('-arm64')}/images/latest-public-beta"
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
    codename = codename.removesuffix("-arm64")
    try:
        max(file for file in local.glob(f"{codename}*") if file.is_dir())
    except ValueError:
        log.critical("*_platform_* directory missing in '%s'", local)
        log.info("Restoring Runtime Platform...")
        _restore_umu(
            local,
            runtime_ver,
            session_pools,
            lambda: len([file for file in local.glob(f"{codename}*") if file.is_dir()])
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
    if not local.joinpath("VERSIONS.txt").is_file():
        log.critical("VERSIONS.txt file missing in '%s'", local)
        log.info("Restoring Runtime Platform...")
        _restore_umu(
            local,
            runtime_ver,
            session_pools,
            lambda: local.joinpath("VERSIONS.txt").is_file(),
        )
        return

    # Fetch the VERSION.txt data
    url: str = f"{host}{endpoint}/VERSION.txt{token}"
    log.debug("Sending request to '%s' for 'VERSION.txt'...", url)
    resp = http_pool.request(HTTPMethod.GET.value, url)
    if resp.status != HTTPStatus.OK:
        log.error("%s returned the status: %s", resp.getheader("Host"), resp.status)
        return

    # Update our runtime
    _update_umu_platform(local, runtime_ver, session_pools, resp)

    log.info("%s is up to date", variant)


def check_runtime(src: Path, runtime_ver: RuntimeVersion) -> int:
    """Validate the file hierarchy of the runtime platform.

    The mtree file included in the Steam runtime platform will be used to
    validate the integrity of the runtime's metadata after its moved to the
    home directory and used to run games.
    """
    runtime: Path
    codename, variant, _ = runtime_ver
    pv_verify: Path = src.joinpath("pressure-vessel", "bin", "pv-verify")
    ret: int = 1

    # Find the runtime directory
    codename = codename.removesuffix("-arm64")
    try:
        runtime = max(file for file in src.glob(f"{codename}*") if file.is_dir())
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
    lock: str = f"{local.parent}/{FileLock.Runtime.value}"
    with unix_flock(lock):
        log.debug("Acquired file lock '%s'...", lock)
        if callback_fn():
            log.debug("Released file lock '%s'", lock)
            log.info("%s was restored", runtime_ver[1])
            return
        _install_umu(runtime_ver, session_pools, local)
        log.debug("Released file lock '%s'", lock)


def _update_umu_platform(
    local: Path,
    runtime_ver: RuntimeVersion,
    session_pools: SessionPools,
    resp: BaseHTTPResponse,
) -> None:
    _, variant, _ = runtime_ver
    version: bytes = resp.data.strip()  # VERSION.txt
    lock: str = f"{local.parent}/{FileLock.Runtime.value}"
    versions: bytes  # VERSIONS.txt

    # Update to the latest platform by checking if the VERSION.txt value
    # exists in VERSIONS.txt
    log.debug("Acquiring file lock '%s'...", lock)
    with unix_flock(lock):
        log.debug("Acquired file lock '%s'", lock)
        # Once another process acquires the lock, check if the latest
        # runtime has already been downloaded
        versions = local.joinpath("VERSIONS.txt").read_bytes()
        if version in versions:
            log.debug("Released file lock '%s'", lock)
            return
        log.info("Updating %s to latest...", variant)
        _install_umu(runtime_ver, session_pools, local)
        log.debug("Released file lock '%s'", lock)


@dataclass
class UmuRuntime:
    """Holds information about a runtime."""

    name: str
    variant: str
    appid: str
    path: Path | None = None

    def __post_init__(self) -> None:  # noqa: D105
        if not self.variant:
            return
        if self.path is None:
            self.path = UMU_LOCAL.joinpath(self.variant)

    def __bool__(self) -> bool:
        """Return if the runtime's path has been populated."""
        return self.path is not None and self.path.is_dir() and self.path.joinpath("mtree.txt.gz").is_file()

    def as_tuple(self) -> RuntimeVersion:
        """Return runtime information as tuple."""
        return self.name, self.variant, self.appid


RUNTIME_VERSIONS = {
    "host": UmuRuntime("host", "", ""),
}

RUNTIME_VERSIONS.update({
    "1391110": UmuRuntime("soldier",        "steamrt2",       "1391110"),
    "1628350": UmuRuntime("sniper",         "steamrt3",       "1628350"),
    "3810310": UmuRuntime("sniper-arm64",   "steamrt3-arm64", "3810310"),
    "4183110": UmuRuntime("steamrt4",       "steamrt4",       "4183110"),
    "4185400": UmuRuntime("steamrt4-arm64", "steamrt4-arm64", "4185400"),
})

if platform.machine() == "x86_64":  # noqa: SIM114
    pass
elif platform.machine() == "aarch64":
    pass
else:
    err: str = f"Unsupported platform {platform.machine()}"
    raise RuntimeError(err)


RUNTIME_NAMES = {RUNTIME_VERSIONS[key].name: key for key in RUNTIME_VERSIONS}


class CompatLayer:
    """Class to describe a Steam compatibility layer."""

    def __init__(self, path: Path, shim: Path) -> None:
        """Create a CompatLayer for a Steam compatibiltiy tool.

        path: the path to the folder containing 'toolmanifest.vdf'
        shim: the path to umu's shim
        resolve: whether to resolve the full chain of compatibility tools required to execute this tools correctly.
        """
        self.tool_path = path.as_posix()
        with Path(path).joinpath("toolmanifest.vdf").open(encoding="utf-8") as f:
            self.tool_manifest = vdf.load(f)["manifest"]

        if path.joinpath("compatibilitytool.vdf").exists():
            with path.joinpath("compatibilitytool.vdf").open(encoding="utf-8") as f:
                # There can be multiple tools definitions in `compatibilitytools.vdf`
                # Take the first one and hope it is the one with the correct display_name
                compat_tools = tuple(vdf.load(f)["compatibilitytools"]["compat_tools"].values())
                self.compatibility_tool = compat_tools[0]
        else:
            self.compatibility_tool = {"display_name": path.name}

        self._runtime: CompatLayer | None = None
        self._shim = shim

    def _resolve(self, shim: Path) -> "CompatLayer | None":
        """Construct and provide the concrete CompatLayer this layer depends on."""
        if self.required_tool_appid is not None and self.required_runtime.path is not None:
            return CompatLayer(self.required_runtime.path, shim)
        return None

    @property
    def runtime(self) -> "CompatLayer | None":
        """Test."""
        if not self._runtime:
            self._runtime = self._resolve(self._shim)
        return self._runtime

    @property
    def required_tool_appid(self) -> str | None:
        """Report the appid of the tool this CompatLayer requires."""
        return str(ret) if (ret := self.tool_manifest.get("require_tool_appid")) else None

    @property
    def required_runtime(self) -> UmuRuntime:
        """Map the required tool's appid to a runtime known by umu."""
        if self.required_tool_appid is None:
            return RUNTIME_VERSIONS["host"]
        return RUNTIME_VERSIONS[self.required_tool_appid]

    @property
    def layer_name(self) -> str:  # noqa: D102
        return str(ret) if (ret := self.tool_manifest.get("compatmanager_layer_name")) else ""

    @property
    def launcher_service(self) -> str:
        """Report the correct layer name for STEAM_COMPAT_LAUNCER_SERVICE."""
        service = self.layer_name
        if service == "umu-passthrough" and self.runtime is not None:
            service = self.runtime.launcher_service
        return service

    @property
    def launch_client(self) -> str | None:
        """Expose pv's launch-client path depending on the tool's container runtime."""
        if self.layer_name == "container-runtime":
            return f"{self.tool_path}/pressure-vessel/bin/steam-runtime-launch-client"
        if self.runtime:
            return self.runtime.launch_client
        return None

    @property
    def is_proton(self) -> bool:
        """Report if this CompatLayer is a Proton."""
        return self.layer_name == "proton"

    @property
    def display_name(self) -> str | None:
        """Report the name of this CompatLayer as set in its manifest."""
        return str(ret) if (ret := self.compatibility_tool.get("display_name")) else None

    @property
    def has_runtime(self) -> bool:
        """Report if the compatibility tool has a configured runtime."""
        return self.runtime is not None

    def _unwrapped_cmd(self, verb: str) -> list[str]:
        """Return the tool specific entry point."""
        tool_path = os.path.normpath(self.tool_path)
        cmd = "".join([shlex.quote(tool_path), self.tool_manifest["commandline"]])
        # Temporary override entry point for backwards compatibility
        if self.layer_name == "container-runtime":
            cmd = cmd.replace("_v2-entry-point", "umu")
        cmd = cmd.replace("%verb%", verb)
        return shlex.split(cmd)

    def _wrapped_cmd(self, verb: str) -> list[str]:
        """Return the fully qualified command for the runtime.

        If the runtime uses another runtime, its entry point is prepended to the local command.
        """
        log.info("Running '%s' using runtime '%s'", self.display_name, self.required_runtime.name)
        cmd = self.runtime.command(verb, unwrapped=False) if self.runtime is not None else []
        target = self._unwrapped_cmd(verb)
        if self.layer_name == "container-runtime":
            cmd.extend([*target, self._shim.as_posix()])
        elif self.runtime is None:
            cmd.extend([self._shim.as_posix(), *target])
        else:
            cmd.extend(target)
        return cmd

    def command(self, verb:str, *, unwrapped: bool) -> list[str]:
        """Return the tool's fully qualified (wrapped) or tool specific (unwrapped) entry point."""
        if unwrapped:
            return self._unwrapped_cmd(verb)
        return self._wrapped_cmd(verb)

    def as_str(self, verb: str):  # noqa: D102
        return " ".join(map(shlex.quote, self.command(verb, unwrapped=False)))

