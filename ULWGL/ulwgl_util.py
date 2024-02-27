import os
from errno import EXDEV, ENOSYS, EINVAL
from ulwgl_consts import Color, Level, CONFIG
from typing import Any, Callable, Dict
from json import load, dump
from shutil import rmtree, copyfile
from ulwgl_log import log
from sys import stderr
from pathlib import Path
from pwd import struct_passwd, getpwuid


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


def msg(msg: Any, level: Level):
    """Return a log message depending on the log level.

    The message will bolden the typeface and apply a color.
    Expects the first parameter to be a string or implement __str__
    """
    log: str = ""

    if level == Level.INFO:
        log = f"{Color.BOLD.value}{Color.INFO.value}{msg}{Color.RESET.value}"
    elif level == Level.WARNING:
        log = f"{Color.BOLD.value}{Color.WARNING.value}{msg}{Color.RESET.value}"
    elif level == Level.DEBUG:
        log = f"{Color.BOLD.value}{Color.DEBUG.value}{msg}{Color.RESET.value}"

    return log


def setup_ulwgl(root: Path, local: Path) -> None:
    """Copy the launcher and its tools to ~/.local/share/ULWGL.

    Parameters are expected to be /usr/share/ULWGL and ~/.local/share/ULWGL respectively
    Performs full copies of tools on new installs and selectively on new updates
    The tools that will be copied are: Pressure Vessel, Reaper, SteamRT, ULWLG launcher and the ULWGL-Runner
    The ULWGL-Runner will be copied to .local/share/Steam/compatibilitytools.d
    """
    log.debug(msg(f"Root: {root}", Level.DEBUG))
    log.debug(msg(f"Local: {local}", Level.DEBUG))

    json: Dict[str, Any] = None
    steam_compat: Path = Path.home().joinpath(".local/share/Steam/compatibilitytools.d")

    if root.name == "app":
        ulwgl_path = root / "share/ULWGL"
    else:
        ulwgl_path = Path("/usr/share/ULWGL")

    # Ensure the path is absolute
    ulwgl_path = ulwgl_path.resolve()

    json = _get_json(ulwgl_path, CONFIG)

    # New install
    # Be lazy and don't implement fallback mechanisms
    if not local.exists():
        return _install_ulwgl(ulwgl_path, local, steam_compat, json)

    return _update_ulwgl(ulwgl_path, local, steam_compat, json, _get_json(local, CONFIG))


def _install_ulwgl(
    root: Path, local: Path, steam_compat: Path, json: Dict[str, Any]
) -> None:
    """For new installations, copy all of the ULWGL tools at a user-writable location.

    The designated locations to copy to will be: ~/.local/share/ULWGL, ~/.local/share/Steam/compatibilitytools.d
    The tools that will be copied are: SteamRT, Pressure Vessel, ULWGL-Runner, ULWGL Launcher files, Reaper and ULWGL_VERSION.json
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

    # Pressure vessel
    print(f"Copying pressure vessel -> {local} ...", file=stderr)
    copyfile_tree(root.joinpath("pressure-vessel"), local.joinpath("pressure-vessel"))

    # Reaper
    print(f"Copying reaper -> {local}", file=stderr)
    cp(root.joinpath("reaper"), local.joinpath("reaper"))

    # Runtime platform
    print(f"Copying runtime -> {local} ...", file=stderr)
    copyfile_tree(
        root.joinpath(json["ulwgl"]["versions"]["runtime_platform"]),
        local.joinpath(json["ulwgl"]["versions"]["runtime_platform"]),
    )

    # _v2-entry-point
    cp(root.joinpath("ULWGL"), local.joinpath("ULWGL"))

    # Auto-generated files
    for file in root.glob("run*"):
        cp(file, local.joinpath(file.name))

    # Launcher files
    for file in root.glob("*.py"):
        if not file.name.startswith("ulwgl_test"):
            print(f"Copying {file} -> {local} ...", file=stderr)
            cp(file, local.joinpath(file.name))

    local.joinpath("ulwgl-run").symlink_to("ulwgl_run.py")

    # Runner
    steam_compat.mkdir(parents=True, exist_ok=True)

    print(f"Copying ULWGL-Runner -> {steam_compat} ...", file=stderr)
    copyfile_tree(root.joinpath("ULWGL-Runner"), steam_compat.joinpath("ULWGL-Runner"))

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

                copyfile_tree(
                    root.joinpath(json_root["ulwgl"]["versions"]["runtime_platform"]),
                    local.joinpath(json_root["ulwgl"]["versions"]["runtime_platform"]),
                )

                # _v2-entry-point
                local.joinpath("ULWGL").unlink(missing_ok=True)
                cp(root.joinpath("ULWGL"), local.joinpath("ULWGL"))

                # Auto-generated files
                for file in local.glob("run*"):
                    file.unlink(missing_ok=True)
                    cp(root.joinpath(file.name), local.joinpath(file.name))

                # Reaper
                # We copy it as it will ideally be built within the runtime platform
                cp(root.joinpath("reaper"), local.joinpath("reaper"))
            elif local.joinpath(runtime).is_dir() and val != runtime:
                # Update
                print(f"Updating {key} to {val} ...", file=stderr)

                rmtree(local.joinpath(runtime).as_posix())
                copyfile_tree(
                    root.joinpath(val),
                    local.joinpath(val),
                )

                local.joinpath("ULWGL").unlink(missing_ok=True)
                cp(root.joinpath("ULWGL"), local.joinpath("ULWGL"))

                for file in local.glob("run*"):
                    file.unlink(missing_ok=True)
                    cp(root.joinpath(file.name), local.joinpath(file.name))

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
            if not steam_compat.joinpath("ULWGL-Runner").is_dir():
                print(
                    f"ULWGL-Runner not found\nCopying ULWGL-Runner -> {steam_compat} ...",
                    file=stderr,
                )

                copyfile_tree(
                    root.joinpath("ULWGL-Runner"), steam_compat.joinpath("ULWGL-Runner")
                )
            elif steam_compat.joinpath("ULWGL-Runner").is_dir() and val != runner:
                # Update
                print(f"Updating {key} to {val} ...", file=stderr)

                rmtree(steam_compat.joinpath("ULWGL-Runner").as_posix())
                copyfile_tree(
                    root.joinpath("ULWGL-Runner"), steam_compat.joinpath("ULWGL-Runner")
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
    # TODO Account for multiple root paths because of Flatpak
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
    """Copy the directory tree from a source to a destination, overwriting existing files."""
    for file in src.iterdir():
        if file.is_dir():
            dest_subdir = dest / file.name
            dest_subdir.mkdir(parents=True, exist_ok=True)
            copyfile_tree(file, dest_subdir)
        else:
            shutil.copy2(file, dest / file.name)
    return True
