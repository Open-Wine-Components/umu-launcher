import os
import tarfile
import subprocess
import re

from errno import EXDEV, ENOSYS, EINVAL
from ulwgl_consts import CONFIG
from typing import Any, Callable, Dict
from json import load, dump
from ulwgl_log import log
from sys import stderr
from pathlib import Path
from pwd import struct_passwd, getpwuid
from shutil import rmtree, move, copyfile, which


class UnixUser:
    """Represents the User of the system as determined by the password database rather than environment variables or file system paths."""

    def __init__(self):
        """Immutable properties of the user determined by the password database that's derived from the real user id."""
        uid: int = os.getuid()
        entry: struct_passwd = getpwuid(uid)
        # Immutable properties, hence no setters
        self.name: str = entry.pw_name
        self.puid: str = entry.pw_uid  # Should be equivalent to the value from getuid
        self.dir: str = entry.pw_dir
        self.is_user: bool = self.puid == uid

    def get_home_dir(self) -> Path:
        """User home directory as determined by the password database that's derived from the current process's real user id."""
        return Path(self.dir).as_posix()

    def get_user(self) -> str:
        """User (login name) as determined by the password database that's derived from the current process's real user id."""
        return self.name

    def get_puid(self) -> int:
        """Numerical user ID as determined by the password database that's derived from the current process's real user id."""
        return self.puid

    def is_user(self, uid: int) -> bool:
        """Compare the UID passed in to this instance."""
        return uid == self.puid


def force_rename(src: Path, dst: Path):  # noqa: D103
    if dst.exists():
        dst.unlink(missing_ok=True)
    src.rename(dst)


def setup_runtime(root: Path, json: Dict[str, Any]) -> None:  # noqa: D103
    # Access the 'runtime_platform' value
    runtime_platform_value: str = json["ulwgl"]["versions"]["runtime_platform"]

    # Assuming runtime_platform_value is "sniper_platform_0.20240125.75305"
    # Split the string at 'sniper_platform_'
    # TODO Change logic so we don't split on a hardcoded string
    version: str = runtime_platform_value.split("sniper_platform_")[1]
    log.debug(msg(f"Version: {version}", Level.DEBUG))

    # Step  1: Define the URL of the file to download
    base_url: str = f"https://repo.steampowered.com/steamrt3/images/{version}/steam-container-runtime-complete.tar.gz"
    log.debug(msg(f"Url: {base_url}", Level.DEBUG))

    # Command to download the file and pipe the progress to Zenity
    download_command: str = f"curl -LJ --progress-bar {base_url} -o /tmp/steam-container-runtime-complete.tar.gz"
    log.debug(msg(f"Download: {download_command}", Level.DEBUG))

    bin: str = which("zenity")

    if not bin:
        err: str = "Zenity is not installed in system.\nPlease install zenity"
        raise FileNotFoundError(err)

    # Execute the command and pipe the output to Zenity
    with subprocess.Popen(
        download_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    ) as proc:
        # Start Zenity with a pipe to its standard input
        zenity_proc: subprocess.Popen = subprocess.Popen(
            [
                f"{bin}",
                "--progress",
                "--auto-close",
                "--text=Downloading Runtime, please wait...",
                "--percentage=0",
            ],
            stdin=subprocess.PIPE,
        )

        for line in iter(proc.stdout.readline, b""):
            # Parse the output to extract the progress percentage
            if b"%" in line:
                line_str = line.decode("utf-8")
                match = re.search(r"(\d+)%", line_str)
                if match:
                    percentage = match.group(1)
                    # Send the percentage to Zenity's standard input
                    zenity_proc.stdin.write(percentage.encode("utf-8") + b"\n")
                    zenity_proc.stdin.flush()

        # Close the Zenity process's standard input
        zenity_proc.stdin.close()
        zenity_proc.wait()

    # Assuming the file is downloaded to '/tmp/steam-container-runtime-complete.tar.gz'
    tar_path: str = "/tmp/steam-container-runtime-complete.tar.gz"

    log.debug(msg(f"Opening: {tar_path}", Level.DEBUG))

    # Open the tar file
    with tarfile.open(tar_path, "r:gz") as tar:
        # Ensure the target directory exists
        Path.home().joinpath(".local", "share", "ULWGL").mkdir(
            parents=True, exist_ok=True
        )

        # Extract the 'depot' folder to the target directory
        log.debug(msg("Extracting archive files -> /tmp", Level.DEBUG))
        for member in tar.getmembers():
            if member.name.startswith("steam-container-runtime/depot/"):
                tar.extract(member, path="/tmp")

        # Step  4: move the files to the correct location
        source_dir: Path = Path("/tmp", "steam-container-runtime", "depot")
        destination_dir: Path = Path.home().joinpath(".local", "share", "ULWGL")

        log.debug(msg(f"Source: {source_dir}", Level.DEBUG))
        log.debug(msg(f"Dest: {destination_dir}", Level.DEBUG))

        # Move each file to the destination directory, overwriting if it exists
        for file in source_dir.glob("*"):
            src_file: Path = source_dir.joinpath(file.name)
            dest_file: Path = destination_dir.joinpath(file.name)

            if dest_file.is_file() or dest_file.is_symlink():
                log.debug(msg(f"Removing file: {dest_file}", Level.DEBUG))
                dest_file.unlink()
            elif dest_file.is_dir():
                log.debug(msg(f"Removing directory: {dest_file}", Level.DEBUG))
                if dest_file.exists():
                    rmtree(dest_file.as_posix())  # remove dir and all contains

            log.debug(msg(f"Moving {src_file} -> {dest_file}", Level.DEBUG))
            move(src_file.as_posix(), dest_file.as_posix())

        # Remove the extracted directory and all its contents
        log.debug(msg("Removing: /tmp/steam-container-runtime", Level.DEBUG))
        if Path("/tmp/steam-container-runtime/").exists():
            rmtree("/tmp/steam-container-runtime/")

        log.debug(msg("Renaming: _v2-entry-point -> ULWGL", Level.DEBUG))
        force_rename(
            destination_dir.joinpath("_v2-entry-point"),
            destination_dir.joinpath("ULWGL"),
        )


def setup_ulwgl(root: Path, local: Path) -> None:
    """Copy the launcher and its tools to ~/.local/share/ULWGL.

    Performs full copies of tools on new installs and selectively on new updates
    The tools that will be copied are: Pressure Vessel, Reaper, SteamRT, ULWLG launcher and the ULWGL-Launcher
    The ULWGL-Launcher will be copied to .local/share/Steam/compatibilitytools.d
    """
    log.debug(msg(f"Root: {root}", Level.DEBUG))
    log.debug(msg(f"Local: {local}", Level.DEBUG))

    json: Dict[str, Any] = None
    steam_compat: Path = Path.home().joinpath(".local/share/Steam/compatibilitytools.d")

    json = _get_json(root, CONFIG)

    # New install
    # Be lazy and don't implement fallback mechanisms
    if not local.exists():
        return _install_ulwgl(root, local, steam_compat, json)

    return _update_ulwgl(root, local, steam_compat, json, _get_json(local, CONFIG))


def _install_ulwgl(
    root: Path, local: Path, steam_compat: Path, json: Dict[str, Any]
) -> None:
    """For new installations, copy all of the ULWGL tools at a user-writable location.

    The designated locations to copy to will be: ~/.local/share/ULWGL, ~/.local/share/Steam/compatibilitytools.d
    The tools that will be copied are: SteamRT, Pressure Vessel, ULWGL-Launcher, ULWGL Launcher files, Reaper and ULWGL_VERSION.json
    """
    cp: Callable[Path, Path] = None

    if hasattr(os, "copy_file_range"):
        log.debug(msg("CoW filesystem detected", Level.DEBUG))
        cp = copyfile_reflink
    else:
        cp = copyfile

    log.debug(msg("New install detected", Level.DEBUG))

    local.mkdir(parents=True, exist_ok=True)

    # Config
    print(f"Copying {CONFIG} -> {local} ...", file=stderr)
    cp(root.joinpath(CONFIG), local.joinpath(CONFIG))

    # Reaper
    print(f"Copying reaper -> {local}", file=stderr)
    cp(root.joinpath("reaper"), local.joinpath("reaper"))

    # Runtime platform
    setup_runtime(root, json)

    # Launcher files
    for file in root.glob("*.py"):
        if not file.name.startswith("ulwgl_test"):
            print(f"Copying {file} -> {local} ...", file=stderr)
            cp(file, local.joinpath(file.name))

    local.joinpath("ulwgl-run").symlink_to("ulwgl_run.py")

    # Runner
    steam_compat.mkdir(parents=True, exist_ok=True)

    print(f"Copying ULWGL-Launcher -> {steam_compat} ...", file=stderr)

    # Remove existing files if they exist -- this is a clean install.
    if steam_compat.joinpath("ULWGL-Launcher").is_dir():
        rmtree(steam_compat.joinpath("ULWGL-Launcher").as_posix())

    copyfile_tree(
        root.joinpath("ULWGL-Launcher"), steam_compat.joinpath("ULWGL-Launcher")
    )

    steam_compat.joinpath("ULWGL-Launcher", "ulwgl-run").symlink_to(
        "../../../ULWGL/ulwgl-run"
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

    The root configuration file (ULWGL_VERSION.json) saved in /usr/share/ULWGL will determine whether an update will be performed or not
    This happens by way of comparing the key/values of the local ULWGL_VERSION.json against the root configuration file
    In the case that the writable directories we copy to are in a partial state, a best effort is made to restore the missing files
    """
    cp: Callable[Path, Path] = None

    if hasattr(os, "copy_file_range"):
        log.debug(msg("CoW filesystem detected", Level.DEBUG))
        cp = copyfile_reflink
    else:
        cp = copyfile

    log.debug(msg("Existing install detected", Level.DEBUG))

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

                cp(root.joinpath("reaper"), local.joinpath("reaper"))

            # Update
            if val != reaper:
                print(f"Updating {key} to {reaper} ...", file=stderr)

                local.joinpath("reaper").unlink(missing_ok=True)
                cp(root.joinpath("reaper"), local.joinpath("reaper"))

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

                copyfile_tree(
                    root.joinpath("pressure-vessel"), local.joinpath("pressure-vessel")
                )
            elif local.joinpath("pressure-vessel").is_dir() and val != pv:
                # Update
                print(f"Updating {key} to {val} ...", file=stderr)

                rmtree(local.joinpath("pressure-vessel").as_posix())
                copyfile_tree(
                    root.joinpath("pressure-vessel"), local.joinpath("pressure-vessel")
                )

                json_local["ulwgl"]["versions"]["pressure_vessel"] = val
        elif key == "runtime_platform":
            # Old runtime
            runtime: str = json_local["ulwgl"]["versions"]["runtime_platform"]

            # Directory is absent
            if not (local.joinpath(runtime).is_dir() or local.joinpath(val).is_dir()):
                print(
                    f"Runtime Platform not found\nCopying {val} -> {local} ...",
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
                print(f"Updating {key} to {launcher} ...", file=stderr)

                # Python files
                for file in root.glob("*.py"):
                    if not file.name.startswith("ulwgl_test"):
                        local.joinpath(file.name).unlink(missing_ok=True)
                        cp(file, local.joinpath(file.name))

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
                    f"ULWGL-Launcher not found\nCopying ULWGL-Launcher -> {steam_compat} ...",
                    file=stderr,
                )

                copyfile_tree(
                    root.joinpath("ULWGL-Launcher"),
                    steam_compat.joinpath("ULWGL-Launcher"),
                )

                steam_compat.joinpath("ULWGL-Launcher", "ulwgl-run").symlink_to(
                    "../../../ULWGL/ulwgl-run"
                )
            elif steam_compat.joinpath("ULWGL-Launcher").is_dir() and val != runner:
                # Update
                print(f"Updating {key} to {val} ...", file=stderr)

                rmtree(steam_compat.joinpath("ULWGL-Launcher").as_posix())
                copyfile_tree(
                    root.joinpath("ULWGL-Launcher"),
                    steam_compat.joinpath("ULWGL-Launcher"),
                )

                steam_compat.joinpath("ULWGL-Launcher", "ulwgl-run").symlink_to(
                    "../../../ULWGL/ulwgl-run"
                )

                json_local["ulwgl"]["versions"]["runner"] = val

    # Finally, update the local config file
    with local.joinpath(CONFIG).open(mode="w") as file:
        dump(json_local, file, indent=4)


def _get_json(path: Path, config: str) -> Dict[str, Any]:
    """Check the state of the configuration file (ULWGL_VERSION.json) in the given path.

    The configuration files are expected to reside in: /usr/share/ULWGL and ~/.local/share/ULWGL
    """
    json: Dict[str, Any] = None

    # The file in /usr/share/ULWGL should always exist
    if not path.joinpath(config).is_file():
        err: str = f"File not found: {config}\nPlease reinstall the package to recover configuration file"
        raise FileNotFoundError(err)

    with path.joinpath(config).open(mode="r") as file:
        json = load(file)

    # Raise an error if "ulwgl" and "versions" doesn't exist
    if not json or (
        "ulwgl" not in json
        or (not json.get("ulwgl") or "versions" not in json.get("ulwgl"))
    ):
        err: str = f"Failed to load {config} or failed to find valid keys in: {config}\nPlease reinstall the package"
        raise ValueError(err)

    return json


def copyfile_reflink(src: Path, dst: Path) -> None:
    """Create CoW copies of a file to a destination.

    Implementation is from Proton
    """
    dst.parent.mkdir(parents=True, exist_ok=True)

    if src.is_symlink():
        dst.symlink_to(src.readlink())
        return

    with src.open(mode="rb", buffering=0) as source:
        bytes_to_copy: int = os.fstat(source.fileno()).st_size

        try:
            with dst.open(mode="wb", buffering=0) as dest:
                while bytes_to_copy > 0:
                    bytes_to_copy -= os.copy_file_range(
                        source.fileno(), dest.fileno(), bytes_to_copy
                    )
        except OSError as e:
            if e.errno not in (EXDEV, ENOSYS, EINVAL):
                raise
            if e.errno == ENOSYS:
                # Fallback to normal copy
                copyfile(src.as_posix(), dst.as_posix())

        dst.chmod(src.stat().st_mode)


def copyfile_tree(src: Path, dest: Path) -> bool:
    """Copy the directory tree from a source to a destination, overwriting existing files and copying symlinks."""
    for file in src.iterdir():
        if file.is_dir():
            dest_subdir = dest / file.name
            dest_subdir.mkdir(parents=True, exist_ok=True)
            copyfile_tree(file, dest_subdir)
        else:
            copyfile_reflink(file, dest / file.name)

    return True
