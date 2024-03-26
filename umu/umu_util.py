from tarfile import open as tar_open, TarInfo
from os import getuid, environ
from umu_consts import CONFIG, STEAM_COMPAT, UMU_LOCAL
from typing import Any, Dict, List, Callable
from json import load, dump
from umu_log import log
from pathlib import Path
from pwd import struct_passwd, getpwuid
from shutil import rmtree, move, copy, copytree
from umu_plugins import enable_zenity
from urllib.request import urlopen
from ssl import create_default_context
from http.client import HTTPException
from tempfile import mkdtemp
from threading import Thread

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


def setup_runtime(json: Dict[str, Any]) -> None:  # noqa: D103
    archive: str = "steam-container-runtime-complete.tar.gz"
    tmp: Path = Path(mkdtemp())
    # Access the 'runtime_platform' value
    runtime_platform_value: str = json["umu"]["versions"]["runtime_platform"]

    # Assuming runtime_platform_value is "sniper_platform_0.20240125.75305"
    # Split the string at 'sniper_platform_'
    # TODO Change logic so we don't split on a hardcoded string
    version: str = runtime_platform_value.split("sniper_platform_")[1]
    log.debug("Version: %s", version)

    # Step  1: Define the URL of the file to download
    # We expect the archive name to not change
    base_url: str = f"https://repo.steampowered.com/steamrt3/images/{version}/{archive}"
    bin: str = "curl"
    opts: List[str] = [
        "-LJO",
        "--silent",
        f"{base_url}",
        "--output-dir",
        tmp.as_posix(),
    ]
    ret: int = 0  # Exit code from zenity

    log.debug("URL: %s", base_url)

    # Download the runtime
    # Optionally create a popup with zenity
    if environ.get("UMU_ZENITY") == "1":
        msg: str = "Downloading UMU-Runtime ..."
        ret: int = enable_zenity(bin, opts, msg)
        if ret:
            tmp.joinpath(archive).unlink(missing_ok=True)
            log.warning("zenity exited with the status code: %s", ret)
            log.console("Retrying from Python ...")
    if not environ.get("UMU_ZENITY") or ret:
        log.console(f"Downloading {runtime_platform_value}, please wait ...")
        with urlopen(  # noqa: S310
            base_url, timeout=300, context=create_default_context()
        ) as resp:
            if resp.status != 200:
                err: str = (
                    f"Unable to download {hash}\n"
                    f"repo.steampowered.com returned the status: {resp.status}"
                )
                raise HTTPException(err)
            log.debug("Writing: %s", tmp.joinpath(archive))
            with tmp.joinpath(archive).open(mode="wb") as file:
                file.write(resp.read())

    log.debug("Opening: %s", tmp.joinpath(archive))

    # Open the tar file
    with tar_open(tmp.joinpath(archive), "r:gz") as tar:
        if tar_filter:
            log.debug("Using filter for archive")
            tar.extraction_filter = tar_filter
        else:
            log.debug("Using no filter for archive")
            log.warning("Archive will be extracted insecurely")

        # Ensure the target directory exists
        UMU_LOCAL.mkdir(parents=True, exist_ok=True)

        # Extract the 'depot' folder to the target directory
        log.debug("Extracting archive files -> %s", tmp)
        for member in tar.getmembers():
            if member.name.startswith("steam-container-runtime/depot/"):
                tar.extract(member, path=tmp)

        # Step  4: move the files to the correct location
        source_dir = tmp.joinpath("steam-container-runtime", "depot")

        log.debug("Source: %s", source_dir)
        log.debug("Destination: %s", UMU_LOCAL)

        # Move each file to the destination directory, overwriting if it exists
        for file in source_dir.glob("*"):
            src_file: Path = source_dir.joinpath(file.name)
            dest_file: Path = UMU_LOCAL.joinpath(file.name)

            if dest_file.is_file() or dest_file.is_symlink():
                log.debug("Removing file: %s", dest_file)
                dest_file.unlink()
            elif dest_file.is_dir():
                log.debug("Removing directory: %s", dest_file)
                if dest_file.exists():
                    rmtree(dest_file.as_posix())  # remove dir and all contains

            log.debug("Moving %s -> %s", src_file, dest_file)
            move(src_file.as_posix(), dest_file.as_posix())

        # Remove the extracted directory and all its contents
        log.debug("Removing: %s/steam-container-runtime", tmp)
        if tmp.joinpath("steam-container-runtime").exists():
            rmtree(tmp.joinpath("steam-container-runtime").as_posix())

        log.debug("Removing: %s", tmp.joinpath(archive))
        tmp.joinpath(archive).unlink(missing_ok=True)

        log.debug("Renaming: _v2-entry-point -> umu")

        # Rename _v2-entry-point
        UMU_LOCAL.joinpath("_v2-entry-point").rename(UMU_LOCAL.joinpath("umu"))


def setup_umu(root: Path, local: Path) -> None:
    """Copy the launcher and its tools to ~/.local/share/umu.

    Performs full copies of tools on new installs and selectively on new updates
    The tools that will be copied are:
    Pressure Vessel, Reaper, SteamRT, ULWLG launcher and the umu-launcher
    The umu-launcher will be copied to .local/share/Steam/compatibilitytools.d
    """
    log.debug("Root: %s", root)
    log.debug("Local: %s", local)
    json: Dict[str, Any] = _get_json(root, CONFIG)

    # New install or umu dir is empty
    # Be lazy and don't implement fallback mechanisms
    if not local.exists() or not any(local.iterdir()):
        return _install_umu(root, local, STEAM_COMPAT, json)

    return _update_umu(root, local, STEAM_COMPAT, json, _get_json(local, CONFIG))


def _install_umu(
    root: Path, local: Path, steam_compat: Path, json: Dict[str, Any]
) -> None:
    """For new installations, copy all of the umu tools at a user-writable location.

    The designated locations to copy to will be:
    ~/.local/share/umu, ~/.local/share/Steam/compatibilitytools.d

    The tools that will be copied are:
    SteamRT, Pressure Vessel, umu-launcher, umu Launcher files, Reaper
    and umu_version.json
    """
    log.debug("New install detected")
    log.console("Setting up Unified Launcher for Windows Games on Linux ...")

    local.mkdir(parents=True, exist_ok=True)

    # Config
    log.console(f"Copied {CONFIG} -> {local}")
    copy(root.joinpath(CONFIG), local.joinpath(CONFIG))

    # Reaper
    log.console(f"Copied reaper -> {local}")
    copy(root.joinpath("reaper"), local.joinpath("reaper"))

    # Launcher files
    for file in root.glob("*.py"):
        if not file.name.startswith("umu_test"):
            log.console(f"Copied {file} -> {local}")
            copy(file, local.joinpath(file.name))

    local.joinpath("umu-run").symlink_to("umu_run.py")

    # Runner
    log.console(f"Copied umu-launcher -> {steam_compat}")
    steam_compat.mkdir(parents=True, exist_ok=True)
    # Remove existing files if they exist -- this is a clean install.
    if steam_compat.joinpath("umu-launcher").is_dir():
        rmtree(steam_compat.joinpath("umu-launcher").as_posix())
    copytree(
        root.joinpath("umu-launcher"),
        steam_compat.joinpath("umu-launcher"),
        dirs_exist_ok=True,
        symlinks=True,
    )
    steam_compat.joinpath("umu-launcher", "umu-run").symlink_to(
        "../../../umu/umu_run.py"
    )

    # Runtime platform
    setup_runtime(json)

    log.console("Completed.")


def _update_umu(
    root: Path,
    local: Path,
    steam_compat: Path,
    json_root: Dict[str, Any],
    json_local: Dict[str, Any],
) -> None:
    """For existing installations, update the umu tools at a user-writable location.

    The configuration file (umu_version.json) saved in the root dir
    will determine whether an update will be performed or not

    This happens by way of comparing the key/values of the local
    umu_version.json against the root configuration file

    In the case that existing writable directories we copy to are in a partial
    state, a best effort is made to restore the missing files
    """
    thread: Thread = None
    log.debug("Existing install detected")

    # Attempt to copy only the updated versions
    # Compare the local to the root config
    # When a directory for a specific tool doesn't exist, remake the copy
    # Be lazy and just trust the integrity of local
    for key, val in json_root["umu"]["versions"].items():
        if key == "reaper":
            reaper: str = json_local["umu"]["versions"]["reaper"]

            # Directory is absent
            if not local.joinpath("reaper").is_file():
                log.warning("Reaper not found")
                copy(root.joinpath("reaper"), local.joinpath("reaper"))
                log.console(f"Restored {key} to {val} ...")

            # Update
            if val != reaper:
                log.console(f"Updating {key} to {val}")

                local.joinpath("reaper").unlink(missing_ok=True)
                copy(root.joinpath("reaper"), local.joinpath("reaper"))

                json_local["umu"]["versions"]["reaper"] = val
        elif key == "runtime_platform":
            # Old runtime
            runtime: str = json_local["umu"]["versions"]["runtime_platform"]

            # Redownload the runtime if absent or pressure vessel is absent
            if (
                not local.joinpath(runtime).is_dir()
                or not local.joinpath("pressure-vessel").is_dir()
            ):
                # Redownload
                log.warning("Runtime Platform not found")
                if local.joinpath("pressure-vessel").is_dir():
                    rmtree(local.joinpath("pressure-vessel").as_posix())
                if local.joinpath(runtime).is_dir():
                    rmtree(local.joinpath(runtime).as_posix())

                thread = Thread(target=setup_runtime, args=[json_root])
                thread.start()
                log.console(f"Restoring Runtime Platform to {val} ...")
            elif (
                local.joinpath(runtime).is_dir()
                and local.joinpath("pressure-vessel").is_dir()
                and val != runtime
            ):
                # Update
                log.console(f"Updating {key} to {val}")
                rmtree(local.joinpath("pressure-vessel").as_posix())
                rmtree(local.joinpath(runtime).as_posix())
                thread = Thread(target=setup_runtime, args=[json_root])
                thread.start()

                json_local["umu"]["versions"]["runtime_platform"] = val
        elif key == "launcher":
            # Launcher
            is_missing: bool = False
            launcher: str = json_local["umu"]["versions"]["launcher"]

            # Update
            if val != launcher:
                log.console(f"Updating {key} to {val}")

                # Python files
                for file in root.glob("*.py"):
                    if not file.name.startswith("umu_test"):
                        local.joinpath(file.name).unlink(missing_ok=True)
                        copy(file, local.joinpath(file.name))

                # Symlink
                local.joinpath("umu-run").unlink(missing_ok=True)
                local.joinpath("umu-run").symlink_to("umu_run.py")

                json_local["umu"]["versions"]["launcher"] = val
                continue

            # Check for missing files
            for file in root.glob("*.py"):
                if (
                    not file.name.startswith("umu_test")
                    and not local.joinpath(file.name).is_file()
                ):
                    is_missing = True
                    log.warning("Missing %s", file.name)
                    copy(file, local.joinpath(file.name))

            if is_missing:
                log.console(f"Restored {key} to {val}")
                local.joinpath("umu-run").unlink(missing_ok=True)
                local.joinpath("umu-run").symlink_to("umu_run.py")
        elif key == "runner":
            # Runner
            runner: str = json_local["umu"]["versions"]["runner"]

            # Directory is absent
            if not steam_compat.joinpath("umu-launcher").is_dir():
                log.warning("umu-launcher not found")

                copytree(
                    root.joinpath("umu-launcher"),
                    steam_compat.joinpath("umu-launcher"),
                    dirs_exist_ok=True,
                    symlinks=True,
                )

                steam_compat.joinpath("umu-launcher", "umu-run").symlink_to(
                    "../../../umu/umu_run.py"
                )
                log.console(f"Restored umu-launcher to {val}")
            elif steam_compat.joinpath("umu-launcher").is_dir() and val != runner:
                # Update
                log.console(f"Updating {key} to {val}")

                rmtree(steam_compat.joinpath("umu-launcher").as_posix())
                copytree(
                    root.joinpath("umu-launcher"),
                    steam_compat.joinpath("umu-launcher"),
                    dirs_exist_ok=True,
                    symlinks=True,
                )

                steam_compat.joinpath("umu-launcher", "umu-run").symlink_to(
                    "../../../umu/umu_run.py"
                )

                json_local["umu"]["versions"]["runner"] = val

    if thread:
        thread.join()

    # Finally, update the local config file
    with local.joinpath(CONFIG).open(mode="w") as file:
        dump(json_local, file, indent=4)


def _get_json(path: Path, config: str) -> Dict[str, Any]:
    """Check the state of the configuration file (umu_version.json) in the given path.

    The configuration files are expected to reside in:
    a root directory (e.g., /usr/share/umu) and ~/.local/share/umu
    """
    json: Dict[str, Any] = None

    # The file in /usr/share/umu should always exist
    if not path.joinpath(config).is_file():
        err: str = (
            f"File not found: {config}\n"
            "Please reinstall the package to recover configuration file"
        )
        raise FileNotFoundError(err)

    with path.joinpath(config).open(mode="r") as file:
        json = load(file)

    # Raise an error if "umu" and "versions" doesn't exist
    if not json or not json.get("umu") or not json.get("umu").get("versions"):
        err: str = (
            f"Failed to load {config} or 'umu' or 'versions' not in: {config}\n"
            "Please reinstall the package"
        )
        raise ValueError(err)

    return json
