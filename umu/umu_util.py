from sys import version
from tarfile import open as tar_open, TarInfo
from os import environ
from umu_consts import CONFIG, UMU_LOCAL
from typing import Any, Dict, List, Callable
from json import load, dump
from umu_log import log
from pathlib import Path
from shutil import rmtree, move, copy
from umu_plugins import enable_zenity
from urllib.request import urlopen
from ssl import create_default_context, SSLContext
from http.client import HTTPException
from tempfile import mkdtemp
from concurrent.futures import ThreadPoolExecutor, Future
from hashlib import sha256
from subprocess import run

SSL_DEFAULT_CONTEXT: SSLContext = create_default_context()

try:
    from tarfile import tar_filter
except ImportError:
    tar_filter: Callable[[str, str], TarInfo] = None


def setup_runtime(json: Dict[str, Any]) -> None:  # noqa: D103
    tmp: Path = Path(mkdtemp())
    ret: int = 0  # Exit code from zenity
    archive: str = "SteamLinuxRuntime_sniper.tar.xz"  # Archive containing the rt
    runtime_platform_value: str = json["umu"]["versions"]["runtime_platform"]
    codename: str = "steamrt3"
    base_url: str = (
        f"https://repo.steampowered.com/{codename}/images/{runtime_platform_value}"
    )
    log.debug("Version: %s", runtime_platform_value)
    log.debug("URL: %s", base_url)

    # Download the runtime
    # Optionally create a popup with zenity
    if environ.get("UMU_ZENITY") == "1":
        bin: str = "curl"
        opts: List[str] = [
            "-LJO",
            "--silent",
            f"{base_url}/{archive}",
            "--output-dir",
            tmp.as_posix(),
        ]
        msg: str = "Downloading UMU-Runtime ..."
        ret = enable_zenity(bin, opts, msg)
        if ret:
            tmp.joinpath(archive).unlink(missing_ok=True)
            log.warning("zenity exited with the status code: %s", ret)
            log.console("Retrying from Python ...")
    if not environ.get("UMU_ZENITY") or ret:
        digest: str = ""

        # Get the digest for the runtime archive
        with (
            urlopen(  # noqa: S310
                f"{base_url}/SHA256SUMS", timeout=30, context=SSL_DEFAULT_CONTEXT
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
        log.console(f"Downloading {codename} {runtime_platform_value}, please wait ...")
        with (
            urlopen(  # noqa: S310
                f"{base_url}/{archive}", timeout=300, context=SSL_DEFAULT_CONTEXT
            ) as resp,
            tmp.joinpath(archive).open(mode="wb") as file,
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
            log.console(f"{codename} {runtime_platform_value}: SHA256 is OK")
            file.write(data)

    # Open the tar file and move the files
    log.debug("Opening: %s", tmp.joinpath(archive))
    with (
        tar_open(tmp.joinpath(archive), "r:xz") as tar,
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
        futures: List[Future] = [
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
    json: Dict[str, Any] = _get_json(root, CONFIG)

    # New install or umu dir is empty
    if not local.exists() or not any(local.iterdir()):
        return _install_umu(root, local, json)

    return _update_umu(local, json, _get_json(local, CONFIG))


def _install_umu(root: Path, local: Path, json: Dict[str, Any]) -> None:
    """Copy the configuration file and download the runtime.

    The launcher will only copy umu_version.json to ~/.local/share/umu

    The subreaper and the launcher files will remain in the system path
    defined at build time, with the exception of umu-launcher which will be
    installed in $PREFIX/share/steam/compatibilitytools.d
    """
    log.debug("New install detected")
    log.console("Setting up Unified Launcher for Windows Games on Linux ...")
    local.mkdir(parents=True, exist_ok=True)

    # Config
    log.console(f"Copied {CONFIG} -> {local}")
    copy(root.joinpath(CONFIG), local.joinpath(CONFIG))

    # Runtime platform
    setup_runtime(json)


def _update_umu(
    local: Path,
    json_root: Dict[str, Any],
    json_local: Dict[str, Any],
) -> None:
    """For existing installations, update the runtime and umu_version.json.

    The umu_version.json saved in the prefix directory (e.g., /usr/share/umu)
    will determine whether an update will be performed for the runtime or not.
    When umu_version.json at ~/.local/share/umu is different than the one in
    the system path, an update will be performed. If the runtime is missing,
    it will be restored

    Updates to the launcher files or subreaper installed in the system path
    will be reflected in umu_version.json at ~/.local/share/umu each launch
    """
    executor: ThreadPoolExecutor = ThreadPoolExecutor()
    futures: List[Future] = []
    log.debug("Existing install detected")

    for key, val in json_root["umu"]["versions"].items():
        if key == "reaper":
            if val == json_local["umu"]["versions"]["reaper"]:
                continue
            log.console(f"Updating {key} to {val}")
            json_local["umu"]["versions"]["reaper"] = val
        elif key == "runtime_platform":
            current: str = json_local["umu"]["versions"]["runtime_platform"]
            runtime: Path = None

            for dir in local.glob(f"*{current}"):
                log.debug("Current runtime: %s", dir)
                runtime = dir
                break

            # Redownload the runtime if absent
            if not runtime or not local.joinpath("pressure-vessel").is_dir():
                log.warning("Runtime Platform not found")
                if runtime and runtime.is_dir():
                    rmtree(runtime.as_posix())
                if local.joinpath("pressure-vessel").is_dir():
                    rmtree(local.joinpath("pressure-vessel").as_posix())
                futures.append(executor.submit(setup_runtime, json_root))
                log.console(f"Restoring Runtime Platform to {val} ...")
                json_local["umu"]["versions"]["runtime_platform"] = val
            elif (
                runtime
                and local.joinpath("pressure-vessel").is_dir()
                and val != current
            ):
                # Update
                log.console(f"Updating {key} to {val}")
                rmtree(runtime.as_posix())
                rmtree(local.joinpath("pressure-vessel").as_posix())
                futures.append(executor.submit(setup_runtime, json_root))
                json_local["umu"]["versions"]["runtime_platform"] = val
        elif key == "launcher":
            if val == json_local["umu"]["versions"]["launcher"]:
                continue
            log.console(f"Updating {key} to {val}")
            json_local["umu"]["versions"]["launcher"] = val
        elif key == "runner":
            if val == json_local["umu"]["versions"]["runner"]:
                continue
            log.console(f"Updating {key} to {val}")
            json_local["umu"]["versions"]["runner"] = val

    for _ in futures:
        _.result()
    executor.shutdown()

    with local.joinpath(CONFIG).open(mode="w", encoding="utf-8") as file:
        dump(json_local, file, indent=4)


def _get_json(path: Path, config: str) -> Dict[str, Any]:
    """Validate the state of the configuration file umu_version.json in a path.

    The configuration file will be used to update the runtime and it reflects
    the tools currently used by launcher.

    The key/value pairs 'umu' and 'versions' must exist
    """
    json: Dict[str, Any] = None

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


def check_runtime(src: Path, json: Dict[str, Any]) -> int:
    """Validate the file hierarchy of the runtime platform.

    The mtree file included in the Steam runtime platform will be used to
    validate the integrity of the runtime's metadata before its moved to the
    home directory and used to run games

    Validation is intended to only be performed after verifying the integrity
    of the archive and its contents
    """
    runtime_platform_value: str = json["umu"]["versions"]["runtime_platform"]
    codename: str = "steamrt3"
    pv_verify: Path = src.joinpath("pressure-vessel", "bin", "pv-verify")
    ret: int = 1

    if not pv_verify.is_file():
        log.warning("%s %s: validation failed", codename, runtime_platform_value)
        log.warning("pv-verify not in: %s", src)
        return ret

    log.console(f"Verifiying integrity of {codename} {runtime_platform_value} ...")
    ret = run([pv_verify.as_posix(), "--quiet"], check=False).returncode

    if pv_verify.is_file() and ret:
        log.warning("%s %s: validation failed", codename, runtime_platform_value)
        log.debug("pv-verify exited with the status code: %s", run)
    else:
        log.console(f"{codename} {runtime_platform_value}: mtree is OK")

    return ret
