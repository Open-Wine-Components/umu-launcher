from tarfile import open as tar_open, TarInfo
from os import getuid
from ulwgl_consts import CONFIG, STEAM_COMPAT, ULWGL_LOCAL
from typing import Any, Dict, List, Callable
from json import load, dump
from ulwgl_log import log
from sys import stderr
from pathlib import Path
from pwd import struct_passwd, getpwuid
from shutil import rmtree, move, copy, copytree
from ulwgl_plugins import enable_zenity
from urllib.request import urlopen
from ssl import create_default_context
from http.client import HTTPException
from socket import AF_INET, SOCK_DGRAM, socket
from tempfile import mkdtemp

try:
    from tarfile import tar_filter
except ImportError:
    tar_filter: Callable[[str, str], TarInfo] = None


class UnixUser:
    """Represents the User of the system as determined by password db (pwd).

    This contrasts with environment variables or file system paths
    """

    def __init__(self) -> None:
        """Immutable properties of the user determined by pwd.

        Values are derived from the real user id
        """
        uid: int = getuid()
        entry: struct_passwd = getpwuid(uid)
        # Immutable properties, hence no setters
        self.name: str = entry.pw_name
        self.puid: str = entry.pw_uid  # Should be equivalent to the value from getuid
        self.dir: str = entry.pw_dir
        self.is_user: bool = self.puid == uid

    def get_home_dir(self) -> Path:
        """User home directory."""
        return Path(self.dir).as_posix()

    def get_user(self) -> str:
        """Username (login name)."""
        return self.name

    def get_puid(self) -> int:
        """Numerical user ID."""
        return self.puid

    def is_user(self, uid: int) -> bool:
        """Compare the UID passed in to this instance."""
        return uid == self.puid


def setup_runtime(root: Path, json: Dict[str, Any]) -> None:  # noqa: D103
    archive: str = "steam-container-runtime-complete.tar.gz"
    tmp: Path = Path(mkdtemp())
    # Access the 'runtime_platform' value
    runtime_platform_value: str = json["ulwgl"]["versions"]["runtime_platform"]

    # Assuming runtime_platform_value is "sniper_platform_0.20240125.75305"
    # Split the string at 'sniper_platform_'
    # TODO Change logic so we don't split on a hardcoded string
    version: str = runtime_platform_value.split("sniper_platform_")[1]
    log.debug(f"Version: {version}")

    # Step  1: Define the URL of the file to download
    # We expect the archive name to not change
    base_url: str = f"https://repo.steampowered.com/steamrt3/images/{version}/{archive}"
    log.debug(f"URL: {base_url}")

    # Download the runtime
    # Attempt to create a popup with zenity otherwise print
    try:
        bin: str = "curl"
        opts: List[str] = [
            "-LJO",
            "--silent",
            base_url,
            "--output-dir",
            tmp.as_posix(),
        ]

        msg: str = "Downloading Runtime, please wait..."
        enable_zenity(bin, opts, msg)
    except TimeoutError:
        # Without the runtime, the launcher will not work
        # Just exit on timeout or download failure
        err: str = (
            "Unable to download the Steam Runtime\n"
            + "repo.steampowered.com request timed out"
        )
        raise TimeoutError(err)
    except FileNotFoundError:
        log.exception("Exception occurred when enabling Zenity")

        print(f"Downloading {runtime_platform_value} ...", file=stderr)

        # noqa S310 we hardcode the URL and trust it
        with urlopen(base_url, timeout=60, context=create_default_context()) as resp:  # noqa: S310
            if resp.status != 200:
                err: str = (
                    "Unable to download the Steam Runtime\n"
                    + f"repo.steampowered.com returned the status: {resp.status}"
                )
                raise HTTPException(err)
            log.debug(f"Writing: {tmp.joinpath(archive)}")
            with tmp.joinpath(archive).open(mode="wb") as file:
                file.write(resp.read())

    log.debug(f"Opening: {tmp.joinpath(archive)}")

    # Open the tar file
    with tar_open(tmp.joinpath(archive), "r:gz") as tar:
        if tar_filter:
            log.debug("Using filter for archive")
            tar.extraction_filter = tar_filter
        else:
            log.debug("Using no filter for archive")
            log.warning("Archive will be extracted insecurely")

        # Ensure the target directory exists
        ULWGL_LOCAL.mkdir(parents=True, exist_ok=True)

        # Extract the 'depot' folder to the target directory
        log.debug(f"Extracting archive files -> {tmp}")
        for member in tar.getmembers():
            if member.name.startswith("steam-container-runtime/depot/"):
                tar.extract(member, path=tmp)

        # Step  4: move the files to the correct location
        source_dir = tmp.joinpath("steam-container-runtime", "depot")

        log.debug(f"Source: {source_dir}")
        log.debug(f"Destination: {ULWGL_LOCAL}")

        # Move each file to the destination directory, overwriting if it exists
        for file in source_dir.glob("*"):
            src_file: Path = source_dir.joinpath(file.name)
            dest_file: Path = ULWGL_LOCAL.joinpath(file.name)

            if dest_file.is_file() or dest_file.is_symlink():
                log.debug(f"Removing file: {dest_file}")
                dest_file.unlink()
            elif dest_file.is_dir():
                log.debug(f"Removing directory: {dest_file}")
                if dest_file.exists():
                    rmtree(dest_file.as_posix())  # remove dir and all contains

            log.debug(f"Moving {src_file} -> {dest_file}")
            move(src_file.as_posix(), dest_file.as_posix())

        # Remove the extracted directory and all its contents
        log.debug(f"Removing: {tmp}/steam-container-runtime")
        if tmp.joinpath("steam-container-runtime").exists():
            rmtree(tmp.joinpath("steam-container-runtime").as_posix())

        log.debug(f"Removing: {tmp.joinpath(archive)}")
        tmp.joinpath(archive).unlink(missing_ok=True)

        log.debug("Renaming: _v2-entry-point -> ULWGL")

        # Rename _v2-entry-point
        ULWGL_LOCAL.joinpath("_v2-entry-point").rename(ULWGL_LOCAL.joinpath("ULWGL"))


def setup_ulwgl(root: Path, local: Path) -> None:
    """Copy the launcher and its tools to ~/.local/share/ULWGL.

    Performs full copies of tools on new installs and selectively on new updates
    The tools that will be copied are:
    Pressure Vessel, Reaper, SteamRT, ULWLG launcher and the ULWGL-Launcher
    The ULWGL-Launcher will be copied to .local/share/Steam/compatibilitytools.d
    """
    log.debug(f"Root: {root}")
    log.debug(f"Local: {local}")

    try:
        with socket(AF_INET, SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.connect(("1.1.1.1", 53))
    except TimeoutError:
        log.debug("User is offline")
        raise
    except OSError:
        raise

    json: Dict[str, Any] = _get_json(root, CONFIG)

    # New install or ULWGL dir is empty
    # Be lazy and don't implement fallback mechanisms
    if not local.exists() or not any(local.iterdir()):
        return _install_ulwgl(root, local, STEAM_COMPAT, json)

    return _update_ulwgl(root, local, STEAM_COMPAT, json, _get_json(local, CONFIG))


def _install_ulwgl(
    root: Path, local: Path, steam_compat: Path, json: Dict[str, Any]
) -> None:
    """For new installations, copy all of the ULWGL tools at a user-writable location.

    The designated locations to copy to will be:
    ~/.local/share/ULWGL, ~/.local/share/Steam/compatibilitytools.d

    The tools that will be copied are:
    SteamRT, Pressure Vessel, ULWGL-Launcher, ULWGL Launcher files, Reaper
    and ULWGL_VERSION.json
    """
    log.debug("New install detected")

    local.mkdir(parents=True, exist_ok=True)

    # Config
    print(f"Copying {CONFIG} -> {local} ...", file=stderr)
    copy(root.joinpath(CONFIG), local.joinpath(CONFIG))

    # Reaper
    print(f"Copying reaper -> {local} ...", file=stderr)
    copy(root.joinpath("reaper"), local.joinpath("reaper"))

    # Runtime platform
    setup_runtime(root, json)

    # Launcher files
    for file in root.glob("*.py"):
        if not file.name.startswith("ulwgl_test"):
            print(f"Copying {file} -> {local} ...", file=stderr)
            copy(file, local.joinpath(file.name))

    local.joinpath("ulwgl-run").symlink_to("ulwgl_run.py")

    # Runner
    steam_compat.mkdir(parents=True, exist_ok=True)

    print(f"Copying ULWGL-Launcher -> {steam_compat} ...", file=stderr)

    # Remove existing files if they exist -- this is a clean install.
    if steam_compat.joinpath("ULWGL-Launcher").is_dir():
        rmtree(steam_compat.joinpath("ULWGL-Launcher").as_posix())

    copytree(
        root.joinpath("ULWGL-Launcher"),
        steam_compat.joinpath("ULWGL-Launcher"),
        dirs_exist_ok=True,
        symlinks=True,
    )

    steam_compat.joinpath("ULWGL-Launcher", "ulwgl-run").symlink_to(
        "../../../ULWGL/ulwgl_run.py"
    )

    print("Completed.", file=stderr)


def _update_ulwgl(
    root: Path,
    local: Path,
    steam_compat: Path,
    json_root: Dict[str, Any],
    json_local: Dict[str, Any],
) -> None:
    """For existing installations, update the ULWGL tools at a user-writable location.

    The configuration file (ULWGL_VERSION.json) saved in the root dir
    will determine whether an update will be performed or not

    This happens by way of comparing the key/values of the local
    ULWGL_VERSION.json against the root configuration file

    In the case that existing writable directories we copy to are in a partial
    state, a best effort is made to restore the missing files
    """
    log.debug("Existing install detected")

    # Attempt to copy only the updated versions
    # Compare the local to the root config
    # When a directory for a specific tool doesn't exist, remake the copy
    # Be lazy and just trust the integrity of local
    for key, val in json_root["ulwgl"]["versions"].items():
        if key == "reaper":
            reaper: str = json_local["ulwgl"]["versions"]["reaper"]

            # Directory is absent
            if not local.joinpath("reaper").is_file():
                print(
                    f"Reaper not found\nCopying {key} -> {local} ...",
                    file=stderr,
                )

                copy(root.joinpath("reaper"), local.joinpath("reaper"))

            # Update
            if val != reaper:
                print(f"Updating {key} to {val} ...", file=stderr)

                local.joinpath("reaper").unlink(missing_ok=True)
                copy(root.joinpath("reaper"), local.joinpath("reaper"))

                json_local["ulwgl"]["versions"]["reaper"] = val
        elif key == "pressure_vessel":
            # Pressure Vessel
            pv: str = json_local["ulwgl"]["versions"]["pressure_vessel"]

            # Directory is absent
            if not local.joinpath("pressure-vessel").is_dir():
                print(
                    f"Pressure Vessel not found\nCopying {key} -> {local} ...",
                    file=stderr,
                )

                copytree(
                    root.joinpath("pressure-vessel"),
                    local.joinpath("pressure-vessel"),
                    dirs_exist_ok=True,
                    symlinks=True,
                )
            elif local.joinpath("pressure-vessel").is_dir() and val != pv:
                # Update
                print(f"Updating {key} to {val} ...", file=stderr)

                rmtree(local.joinpath("pressure-vessel").as_posix())
                copytree(
                    root.joinpath("pressure-vessel"),
                    local.joinpath("pressure-vessel"),
                    dirs_exist_ok=True,
                    symlinks=True,
                )

                json_local["ulwgl"]["versions"]["pressure_vessel"] = val
        elif key == "runtime_platform":
            # Old runtime
            runtime: str = json_local["ulwgl"]["versions"]["runtime_platform"]

            # Directory is absent
            if not (local.joinpath(runtime).is_dir() or local.joinpath(val).is_dir()):
                print(
                    "Runtime Platform not found",
                    file=stderr,
                )

                # Download the runtime from the official source
                setup_runtime(root, json_root)
            elif local.joinpath(runtime).is_dir() and val != runtime:
                # Update
                print(f"Updating {key} to {val} ...", file=stderr)

                rmtree(local.joinpath(runtime).as_posix())
                setup_runtime(root, json_root)

                json_local["ulwgl"]["versions"]["runtime_platform"] = val
        elif key == "launcher":
            # Launcher
            # NOTE: We do not attempt to restore missing launcher files
            launcher: str = json_local["ulwgl"]["versions"]["launcher"]

            if val != launcher:
                print(f"Updating {key} to {val} ...", file=stderr)

                # Python files
                for file in root.glob("*.py"):
                    if not file.name.startswith("ulwgl_test"):
                        local.joinpath(file.name).unlink(missing_ok=True)
                        copy(file, local.joinpath(file.name))

                # Symlink
                local.joinpath("ulwgl-run").unlink(missing_ok=True)
                local.joinpath("ulwgl-run").symlink_to("ulwgl_run.py")

                json_local["ulwgl"]["versions"]["launcher"] = val
        elif key == "runner":
            # Runner
            runner: str = json_local["ulwgl"]["versions"]["runner"]

            # Directory is absent
            if not steam_compat.joinpath("ULWGL-Launcher").is_dir():
                print(
                    "ULWGL-Launcher not found\n"
                    + f"Copying ULWGL-Launcher -> {steam_compat} ...",
                    file=stderr,
                )

                copytree(
                    root.joinpath("ULWGL-Launcher"),
                    steam_compat.joinpath("ULWGL-Launcher"),
                    dirs_exist_ok=True,
                    symlinks=True,
                )

                steam_compat.joinpath("ULWGL-Launcher", "ulwgl-run").symlink_to(
                    "../../../ULWGL/ulwgl_run.py"
                )
            elif steam_compat.joinpath("ULWGL-Launcher").is_dir() and val != runner:
                # Update
                print(f"Updating {key} to {val} ...", file=stderr)

                rmtree(steam_compat.joinpath("ULWGL-Launcher").as_posix())
                copytree(
                    root.joinpath("ULWGL-Launcher"),
                    steam_compat.joinpath("ULWGL-Launcher"),
                    dirs_exist_ok=True,
                    symlinks=True,
                )

                steam_compat.joinpath("ULWGL-Launcher", "ulwgl-run").symlink_to(
                    "../../../ULWGL/ulwgl_run.py"
                )

                json_local["ulwgl"]["versions"]["runner"] = val

    # Finally, update the local config file
    with local.joinpath(CONFIG).open(mode="w") as file:
        dump(json_local, file, indent=4)


def _get_json(path: Path, config: str) -> Dict[str, Any]:
    """Check the state of the configuration file (ULWGL_VERSION.json) in the given path.

    The configuration files are expected to reside in:
    a root directory (e.g., /usr/share/ulwgl) and ~/.local/share/ULWGL
    """
    json: Dict[str, Any] = None

    # The file in /usr/share/ULWGL should always exist
    if not path.joinpath(config).is_file():
        err: str = (
            f"File not found: {config}\n"
            + "Please reinstall the package to recover configuration file"
        )
        raise FileNotFoundError(err)

    with path.joinpath(config).open(mode="r") as file:
        json = load(file)

    # Raise an error if "ulwgl" and "versions" doesn't exist
    if not json or (
        "ulwgl" not in json
        or (not json.get("ulwgl") or "versions" not in json.get("ulwgl"))
    ):
        err: str = (
            f"Failed to load {config} or 'ulwgl' or 'versions' not in: {config}\n"
            + "Please reinstall the package"
        )
        raise ValueError(err)

    return json
