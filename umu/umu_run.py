import os
import sys
import threading
import time
from _ctypes import CFuncPtr
from argparse import Namespace
from array import array
from collections.abc import MutableMapping
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from ctypes import CDLL, c_int, c_ulong
from errno import ENETUNREACH
from mmap import ACCESS_READ, mmap
from zipfile import Path as ZipPath

try:
    from importlib.resources.abc import Traversable
except ModuleNotFoundError:
    from importlib.abc import Traversable


from pathlib import Path
from pwd import getpwuid
from re import match
from socket import AF_INET, SOCK_DGRAM, socket
from subprocess import Popen
from typing import Any

from urllib3 import PoolManager, Retry
from urllib3.exceptions import MaxRetryError, NewConnectionError
from urllib3.exceptions import TimeoutError as TimeoutErrorUrllib3
from urllib3.util import Timeout
from Xlib import X, Xatom, display
from Xlib.error import DisplayConnectionError
from Xlib.protocol.request import GetProperty
from Xlib.protocol.rq import Event
from Xlib.xobject.drawable import Window

from umu import __runtime_version__, __version__
from umu.umu_consts import (
    PR_SET_CHILD_SUBREAPER,
    PROTON_VERBS,
    STEAM_COMPAT,
    STEAM_WINDOW_ID,
    UMU_LOCAL,
    GamescopeAtom,
)
from umu.umu_log import log
from umu.umu_plugins import set_env_toml
from umu.umu_proton import get_umu_proton
from umu.umu_runtime import setup_umu
from umu.umu_util import (
    get_libc,
    get_library_paths,
    has_umu_setup,
    is_installed_verb,
    unix_flock,
    xdisplay,
)

NET_TIMEOUT = 5.0

NET_RETRIES = 1


def setup_pfx(path: str) -> None:
    """Prepare a Proton compatible WINE prefix."""
    pfx: Path = Path(path).joinpath("pfx").expanduser()
    steam: Path = Path(path).expanduser().joinpath("drive_c", "users", "steamuser")
    # Login name of the user as determined by the password database (pwd)
    user: str = getpwuid(os.getuid()).pw_name
    wineuser: Path = Path(path).expanduser().joinpath("drive_c", "users", user)

    if os.environ.get("UMU_NO_PROTON") == "1":
        return

    if pfx.is_symlink():
        pfx.unlink()

    if not pfx.is_dir():
        pfx.symlink_to(Path(path).expanduser().resolve(strict=True))

    Path(path).joinpath("tracked_files").expanduser().touch()

    # Create a symlink of the current user to the steamuser dir or vice versa
    # Default for a new prefix is: unixuser -> steamuser
    if not wineuser.exists() and not steam.exists():
        # For new prefixes with our Proton: user -> steamuser
        steam.mkdir(parents=True)
        wineuser.symlink_to("steamuser")
    elif wineuser.is_dir() and not steam.exists():
        # When there's a user dir: steamuser -> user
        steam.symlink_to(user)
    elif not wineuser.exists() and steam.is_dir():
        wineuser.symlink_to("steamuser")


def check_env(
    env: dict[str, str], session_pools: tuple[ThreadPoolExecutor, PoolManager]
) -> dict[str, str] | dict[str, Any]:
    """Before executing a game, check for environment variables and set them.

    GAMEID is strictly required and the client is responsible for setting this.
    When the client only sets the GAMEID, the WINE prefix directory will be
    created as $HOME/Games/umu/$GAMEID.
    """
    if not os.environ.get("GAMEID"):
        err: str = "Environment variable not set or is empty: GAMEID"
        raise ValueError(err)

    env["GAMEID"] = os.environ["GAMEID"]

    if os.environ.get("WINEPREFIX") == "":
        err: str = "Environment variable is empty: WINEPREFIX"
        raise ValueError(err)

    if os.environ.get("UMU_NO_PROTON") != "1" and "WINEPREFIX" not in os.environ:
        pfx: Path = Path.home().joinpath("Games", "umu", env["GAMEID"])
        pfx.mkdir(parents=True, exist_ok=True)
        os.environ["WINEPREFIX"] = str(pfx)

    if (
        os.environ.get("UMU_NO_PROTON") != "1"
        and not Path(os.environ["WINEPREFIX"]).expanduser().is_dir()
    ):
        pfx: Path = Path(os.environ["WINEPREFIX"])
        pfx.mkdir(parents=True, exist_ok=True)
        os.environ["WINEPREFIX"] = str(pfx)

    env["WINEPREFIX"] = os.environ.get("WINEPREFIX", "")

    # Skip Proton if running a native Linux executable
    if os.environ.get("UMU_NO_PROTON") == "1":
        return env

    path: Path = STEAM_COMPAT.joinpath(os.environ.get("PROTONPATH", ""))
    if os.environ.get("PROTONPATH") and path.name == "UMU-Latest":
        path.unlink(missing_ok=True)

    # Proton Version
    if os.environ.get("PROTONPATH") and path.is_dir():
        os.environ["PROTONPATH"] = str(STEAM_COMPAT.joinpath(os.environ["PROTONPATH"]))

    # Proton Codename
    if os.environ.get("PROTONPATH") in {"GE-Proton", "GE-Latest", "UMU-Latest"}:
        get_umu_proton(env, session_pools)

    if "PROTONPATH" not in os.environ:
        os.environ["PROTONPATH"] = ""
        get_umu_proton(env, session_pools)

    env["PROTONPATH"] = os.environ["PROTONPATH"]

    # If download fails/doesn't exist in the system, raise an error
    if not os.environ["PROTONPATH"]:
        err: str = (
            "Environment variable not set or is empty: PROTONPATH\n"
            f"Possible reason: GE-Proton or UMU-Proton not found in '{STEAM_COMPAT}'"
            " or network error"
        )
        raise FileNotFoundError(err)

    return env


def set_env(
    env: dict[str, str], args: Namespace | tuple[str, list[str]]
) -> dict[str, str]:
    """Set various environment variables for the Steam Runtime."""
    pfx: Path = Path(env["WINEPREFIX"]).expanduser().resolve(strict=True)
    protonpath: Path = Path(env["PROTONPATH"]).expanduser().resolve(strict=True)
    # Command execution usage
    is_cmd: bool = isinstance(args, tuple)
    # Command execution usage, but client wants to create a prefix. When an
    # empty string is the executable, Proton is expected to create the prefix
    # but will fail because the executable is not found
    is_createpfx: bool = (
        (is_cmd and not args[0]) or (is_cmd and args[0] == "createprefix")  # type: ignore
    )
    # Command execution usage, but client wants to run winetricks verbs
    is_winetricks: bool = is_cmd and args[0] == "winetricks"  # type: ignore

    # PROTON_VERB
    # For invalid Proton verbs, just assign the waitforexitandrun
    if os.environ.get("PROTON_VERB") in PROTON_VERBS:
        env["PROTON_VERB"] = os.environ["PROTON_VERB"]
    else:
        env["PROTON_VERB"] = "waitforexitandrun"

    # EXE
    if is_createpfx:
        env["EXE"] = ""
        env["STEAM_COMPAT_INSTALL_PATH"] = ""
    elif is_winetricks:
        # Make an absolute path to winetricks within GE-Proton or UMU-Proton.
        # The launcher will change to the winetricks parent directory before
        # creating the subprocess
        exe: Path = Path(protonpath, "protonfixes", "winetricks").resolve(strict=True)
        env["EXE"] = str(exe)
        args = (env["EXE"], args[1])  # type: ignore
        env["STEAM_COMPAT_INSTALL_PATH"] = str(exe.parent)
    elif is_cmd:
        try:
            # Ensure executable path is absolute, otherwise Proton will fail
            # when creating the subprocess.
            # e.g., Games/umu/umu-0 -> $HOME/Games/umu/umu-0
            exe: Path = Path(args[0]).expanduser().resolve(strict=True)  # type: ignore
            env["EXE"] = str(exe)
            env["STEAM_COMPAT_INSTALL_PATH"] = os.environ.get(
                "STEAM_COMPAT_INSTALL_PATH"
            ) or str(exe.parent)
        except FileNotFoundError:
            # Assume that the executable will be inside prefix or container
            env["EXE"] = args[0]  # type: ignore
            env["STEAM_COMPAT_INSTALL_PATH"] = ""
            log.warning("Executable not found: %s", env["EXE"])
        env["STORE"] = os.environ.get("STORE", "")
    else:  # Configuration file usage
        exe: Path = Path(env["EXE"]).expanduser()
        env["EXE"] = str(exe)
        env["STEAM_COMPAT_INSTALL_PATH"] = str(exe.parent)
        env["STORE"] = env.get("STORE", "")

    # STORE
    stores: set[str] | None = None
    umu_db: Path = protonpath.joinpath("protonfixes", "umu-database.csv")
    if os.environ.get("GAMEID") == "none" and os.environ.get("STORE"):
        stores = {
            store.name.removeprefix("gamefixes-")
            for store in protonpath.joinpath("protonfixes").glob("gamefixes-*")
        }
    if stores and umu_db.is_file() and os.environ.get("STORE") in stores:
        set_umu_id(umu_db, env)

    # UMU_ID
    env["UMU_ID"] = env["GAMEID"]
    env["STEAM_COMPAT_APP_ID"] = "0"

    if match(r"^umu-[\d\w]+$", env["UMU_ID"]):
        env["STEAM_COMPAT_APP_ID"] = env["UMU_ID"][env["UMU_ID"].find("-") + 1 :]
    env["SteamAppId"] = env["STEAM_COMPAT_APP_ID"]
    env["SteamGameId"] = env["SteamAppId"]

    # PATHS
    env["WINEPREFIX"] = str(pfx)
    env["PROTONPATH"] = str(protonpath)
    env["STEAM_COMPAT_DATA_PATH"] = env["WINEPREFIX"]
    env["STEAM_COMPAT_SHADER_PATH"] = f"{env['STEAM_COMPAT_DATA_PATH']}/shadercache"
    env["STEAM_COMPAT_TOOL_PATHS"] = f"{env['PROTONPATH']}:{UMU_LOCAL}"
    env["STEAM_COMPAT_MOUNTS"] = env["STEAM_COMPAT_TOOL_PATHS"]

    # Zenity
    env["UMU_ZENITY"] = os.environ.get("UMU_ZENITY") or ""

    # Game drive
    enable_steam_game_drive(env)

    # Winetricks
    if env.get("EXE", "").endswith("winetricks"):
        env["WINETRICKS_SUPER_QUIET"] = (
            "" if os.environ.get("UMU_LOG") in {"debug", "1"} else "1"
        )

    # Runtime
    env["UMU_NO_RUNTIME"] = os.environ.get("UMU_NO_RUNTIME") or ""
    env["UMU_RUNTIME_UPDATE"] = os.environ.get("UMU_RUNTIME_UPDATE") or ""
    env["UMU_NO_PROTON"] = os.environ.get("UMU_NO_PROTON") or ""

    # Proton logging (to stdout)
    # Check for PROTON_LOG because it redirects output to log file
    if os.environ.get("PROTON_LOG", "0") == "0":
        env["WINEDEBUG"] = os.environ.get("WINEDEBUG") or "+fixme"
        env["DXVK_LOG_LEVEL"] = os.environ.get("DXVK_LOG_LEVEL") or "info"
        env["VKD3D_DEBUG"] = os.environ.get("VKD3D_DEBUG") or "fixme"

    return env


def set_umu_id(umu_db: Path, env: dict[str, str]) -> dict[str, str]:
    """Set the GAMEID given the current title."""
    parts: set[bytes] = {path.encode() for path in Path(env["EXE"]).parts}
    store: bytes = env["STORE"].encode()

    with (
        umu_db.open(mode="rb") as fp,
        mmap(fp.fileno(), length=0, access=ACCESS_READ) as mm,
    ):
        while row := mm.readline():
            columns = row.split(b",")
            if store not in columns[1]:
                row = b""
                continue
            if columns[0] in parts:
                env["GAMEID"] = columns[3].decode()
                break

    return env


def enable_steam_game_drive(env: dict[str, str]) -> dict[str, str]:
    """Enable Steam Game Drive functionality."""
    paths: set[str] = set()
    root: Path = Path("/")

    # Check for mount points going up toward the root
    # NOTE: Subvolumes can be mount points
    for path in Path(env["STEAM_COMPAT_INSTALL_PATH"]).parents:
        if path.is_mount() and path != root:
            if os.environ.get("STEAM_COMPAT_LIBRARY_PATHS"):
                env["STEAM_COMPAT_LIBRARY_PATHS"] = (
                    f"{os.environ['STEAM_COMPAT_LIBRARY_PATHS']}:{path}"
                )
            else:
                env["STEAM_COMPAT_LIBRARY_PATHS"] = str(path)
            break

    if os.environ.get("LD_LIBRARY_PATH"):
        paths = set(os.environ["LD_LIBRARY_PATH"].split(":"))

    if env["STEAM_COMPAT_INSTALL_PATH"]:
        paths.add(env["STEAM_COMPAT_INSTALL_PATH"])

    # Set the shared library paths of the system
    paths |= get_library_paths()

    env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(paths)

    return env


def build_command(
    env: dict[str, str],
    local: Path,
    opts: list[str] = [],
) -> tuple[Path | str, ...]:
    """Build the command to be executed."""
    shim: Path = local.joinpath("umu-shim")
    proton: Path = Path(env["PROTONPATH"], "proton")
    entry_point: Path = local.joinpath("umu")

    if env.get("UMU_NO_PROTON") != "1" and not proton.is_file():
        err: str = "The following file was not found in PROTONPATH: proton"
        raise FileNotFoundError(err)

    # Exit if the entry point is missing
    # The _v2-entry-point script and container framework tools are included in
    # the same image, so this can happen if the image failed to download
    if not entry_point.is_file():
        err: str = (
            f"_v2-entry-point (umu) cannot be found in '{local}'\n"
            "Runtime Platform missing or download incomplete"
        )
        raise FileNotFoundError(err)

    # Winetricks
    if env.get("EXE", "").endswith("winetricks") and opts:
        # The position of arguments matter for winetricks
        # Usage: ./winetricks [options] [command|verb|path-to-verb] ...
        return (
            entry_point,
            "--verb",
            env["PROTON_VERB"],
            "--",
            proton,
            env["PROTON_VERB"],
            env["EXE"],
            "-q",
            *opts,
        )

    # Will run the game within the Steam Runtime w/o Proton
    # Ideally, for reliability, executables should be compiled within
    # the Steam Runtime
    if env.get("UMU_NO_PROTON") == "1":
        return (entry_point, "--verb", env["PROTON_VERB"], "--", env["EXE"], *opts)

    # Will run the game outside the Steam Runtime w/ Proton
    if env.get("UMU_NO_RUNTIME") == "1":
        log.warning("Runtime Platform disabled")
        return proton, env["PROTON_VERB"], env["EXE"], *opts

    return (
        entry_point,
        "--verb",
        env["PROTON_VERB"],
        "--",
        shim,
        proton,
        env["PROTON_VERB"],
        env["EXE"],
        *opts,
    )


def get_window_ids(d: display.Display) -> set[str] | None:
    """Get the list of window ids under the root window for a display."""
    try:
        event: Event = d.next_event()
        if event.type == X.CreateNotify:
            return {child.id for child in d.screen().root.query_tree().children}
    except Exception as e:
        log.exception(e)

    return None


def set_steam_game_property(
    d: display.Display,
    window_ids: set[str],
    steam_assigned_appid: int,
) -> display.Display:
    """Set Steam's assigned app ID on a list of windows."""
    log.debug("Steam app ID: %s", steam_assigned_appid)
    for window_id in window_ids:
        try:
            window: Window = d.create_resource_object("window", int(window_id))
            window.change_property(
                d.get_atom(GamescopeAtom.SteamGame.value),
                Xatom.CARDINAL,
                32,
                [steam_assigned_appid],
            )
            log.debug(
                "Successfully set %s property for window ID: %s",
                GamescopeAtom.SteamGame.value,
                window_id,
            )
        except Exception as e:
            log.error(
                "Error setting %s property for window ID: %s",
                GamescopeAtom.SteamGame.value,
                window_id,
            )
            log.exception(e)

    return d


def get_gamescope_baselayer_appid(
    d: display.Display,
) -> list[int] | None:
    """Get the GAMESCOPECTRL_BASELAYER_APPID value on the primary root window."""
    try:
        root_primary: Window = d.screen().root
        # Intern the atom for GAMESCOPECTRL_BASELAYER_APPID
        atom = d.get_atom(GamescopeAtom.BaselayerAppId.value)
        # Get the property value
        prop: GetProperty | None = root_primary.get_full_property(atom, Xatom.CARDINAL)
        # For GAMESCOPECTRL_BASELAYER_APPID, the value is a u32 array
        if prop and prop.value and isinstance(prop.value, array):
            # Ignore. Converting a u32 array to a list creates a list[int]
            return prop.value.tolist()  # type: ignore
        log.debug("%s property not found", GamescopeAtom.BaselayerAppId.value)
    except Exception as e:
        log.error("Error getting %s property", GamescopeAtom.BaselayerAppId.value)
        log.exception(e)

    return None


def rearrange_gamescope_baselayer_appid(
    sequence: list[int],
) -> tuple[list[int], int] | None:
    """Rearrange the GAMESCOPECTRL_BASELAYER_APPID value retrieved from a window."""
    rearranged: list[int] = list(sequence)
    steam_appid: int = get_steam_appid(os.environ)

    log.debug("%s: %s", GamescopeAtom.BaselayerAppId.value, sequence)

    if not steam_appid:
        # Case when the app ID can't be found from environment variables
        # See https://github.com/Open-Wine-Components/umu-launcher/issues/318
        log.error(
            "Failed to acquire app ID, skipping %s rearrangement",
            GamescopeAtom.BaselayerAppId.value,
        )
        return None

    try:
        rearranged.remove(steam_appid)
    except ValueError as e:
        # Case when the app ID isn't in GAMESCOPECTRL_BASELAYER_APPID
        # One case this can occur is if the client overrides Steam's env vars
        # that we get the app ID from
        log.exception(e)
        return None

    # Steam's window should be last, while assigned app id 2nd to last
    rearranged = [*rearranged[:-1], steam_appid, STEAM_WINDOW_ID]
    log.debug("Rearranging %s", GamescopeAtom.BaselayerAppId.value)
    log.debug("'%s' -> '%s'", sequence, rearranged)

    return rearranged, steam_appid


def set_gamescope_baselayer_appid(
    d: display.Display, rearranged: list[int]
) -> display.Display | None:
    """Set a new gamescope GAMESCOPECTRL_BASELAYER_APPID on the primary root window."""
    try:
        # Intern the atom for GAMESCOPECTRL_BASELAYER_APPID
        atom = d.get_atom(GamescopeAtom.BaselayerAppId.value)
        # Set the property value
        d.screen().root.change_property(atom, Xatom.CARDINAL, 32, rearranged)
        log.debug(
            "Successfully set %s property: %s",
            GamescopeAtom.BaselayerAppId.value,
            ", ".join(map(str, rearranged)),
        )
        return d
    except Exception as e:
        log.error("Error setting %s property", GamescopeAtom.BaselayerAppId.value)
        log.exception(e)

    return None


def get_steam_appid(env: MutableMapping) -> int:
    """Get the Steam app ID from the host environment variables."""
    steam_appid: int = 0

    if path := env.get("STEAM_COMPAT_TRANSCODED_MEDIA_PATH"):
        # Suppress cases when value is not a number or empty tuple
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-1])

    if path := env.get("STEAM_COMPAT_MEDIA_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-2])

    if path := env.get("STEAM_FOSSILIZE_DUMP_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-3])

    if path := env.get("DXVK_STATE_CACHE_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-2])

    return steam_appid


def monitor_baselayer_appid(
    d_primary: display.Display,
    gamescope_baselayer_sequence: list[int],
) -> None:
    """Monitor for broken GAMESCOPECTRL_BASELAYER_APPID values."""
    root_primary: Window = d_primary.screen().root
    rearranged_gamescope_baselayer: tuple[list[int], int] | None = None
    atom = d_primary.get_atom(GamescopeAtom.BaselayerAppId.value)
    root_primary.change_attributes(event_mask=X.PropertyChangeMask)

    log.debug(
        "Monitoring %s property for DISPLAY=%s...",
        GamescopeAtom.BaselayerAppId.value,
        d_primary.get_display_name(),
    )

    # Rearranged GAMESCOPECTRL_BASELAYER_APPID
    rearranged_gamescope_baselayer = rearrange_gamescope_baselayer_appid(
        gamescope_baselayer_sequence
    )

    # Set the rearranged GAMESCOPECTRL_BASELAYER_APPID
    if rearranged_gamescope_baselayer:
        rearranged, _ = rearranged_gamescope_baselayer
        set_gamescope_baselayer_appid(d_primary, rearranged)
        rearranged_gamescope_baselayer = None

    while True:
        event: Event = d_primary.next_event()
        prop: GetProperty | None = None

        if event.type == X.PropertyNotify and event.atom == atom:
            prop = root_primary.get_full_property(atom, Xatom.CARDINAL)

        # Check if the layer sequence has changed to the broken one
        if prop and prop.value[-1] != STEAM_WINDOW_ID:
            log.debug(
                "Broken %s property detected, will rearrange...",
                GamescopeAtom.BaselayerAppId.value,
            )
            log.debug(
                "%s has atom %s: %s",
                GamescopeAtom.BaselayerAppId.value,
                atom,
                prop.value,
            )
            rearranged_gamescope_baselayer = rearrange_gamescope_baselayer_appid(
                prop.value
            )

        if rearranged_gamescope_baselayer:
            rearranged, _ = rearranged_gamescope_baselayer
            set_gamescope_baselayer_appid(d_primary, rearranged)
            rearranged_gamescope_baselayer = None
            continue

        time.sleep(0.1)


def monitor_windows(
    d_secondary: display.Display,
) -> None:
    """Monitor for new windows for a display and assign them Steam's assigned app ID."""
    window_ids: set[str] | None = None
    steam_appid: int = get_steam_appid(os.environ)

    log.debug(
        "Waiting for new windows IDs for DISPLAY=%s...",
        d_secondary.get_display_name(),
    )

    while not window_ids:
        window_ids = get_window_ids(d_secondary)

    set_steam_game_property(d_secondary, window_ids, steam_appid)

    log.debug(
        "Monitoring for new window IDs for DISPLAY=%s...",
        d_secondary.get_display_name(),
    )

    # Check if the window sequence has changed
    while True:
        current_window_ids: set[str] | None = get_window_ids(d_secondary)

        if not current_window_ids:
            continue

        if diff := current_window_ids.difference(window_ids):
            log.debug("New window IDs detected: %s", window_ids)
            log.debug("Current tracked windows IDs: %s", current_window_ids)
            log.debug("Window IDs set difference: %s", diff)
            window_ids |= diff
            set_steam_game_property(d_secondary, diff, steam_appid)


def run_in_steammode(proc: Popen) -> int:
    """Set properties on gamescope windows when running in steam mode.

    Currently, Flatpak apps that use umu as their runtime will not have their
    game window brought to the foreground due to the base layer being out of
    order.

    See https://github.com/ValveSoftware/gamescope/issues/1341
    """
    # GAMESCOPECTRL_BASELAYER_APPID value on the primary's window
    gamescope_baselayer_sequence: list[int] | None = None

    # Currently, steamos creates two xwayland servers at :0 and :1
    # Despite the socket for display :0 being hidden at /tmp/.x11-unix in
    # in the Flatpak, it is still possible to connect to it.
    # TODO: Find a robust way to get gamescope displays both in a container
    # and outside a container
    try:
        with xdisplay(":0") as d_primary, xdisplay(":1") as d_secondary:
            gamescope_baselayer_sequence = get_gamescope_baselayer_appid(d_primary)
            # Dont do window fuckery if we're not inside gamescope
            if (
                gamescope_baselayer_sequence
                and os.environ.get("PROTON_VERB") == "waitforexitandrun"
            ):
                d_secondary.screen().root.change_attributes(
                    event_mask=X.SubstructureNotifyMask
                )

                # Monitor for new windows for the DISPLAY associated with game
                window_thread = threading.Thread(
                    target=monitor_windows, args=(d_secondary,)
                )
                window_thread.daemon = True
                window_thread.start()

                # Monitor for broken GAMESCOPECTRL_BASELAYER_APPID
                baselayer_thread = threading.Thread(
                    target=monitor_baselayer_appid,
                    args=(d_primary, gamescope_baselayer_sequence),
                )
                baselayer_thread.daemon = True
                baselayer_thread.start()
            return proc.wait()
    except DisplayConnectionError as e:
        # Case where steamos changed its display outputs as we're currently
        # assuming connecting to :0 and :1 is stable
        log.exception(e)

    return proc.wait()


def run_command(command: tuple[Path | str, ...]) -> int:
    """Run the executable using Proton within the Steam Runtime."""
    prctl: CFuncPtr
    cwd: Path | str
    proc: Popen
    ret: int = 0
    prctl_ret: int = 0
    libc: str = get_libc()
    is_gamescope_session: bool = (
        os.environ.get("XDG_CURRENT_DESKTOP") == "gamescope"
        or os.environ.get("XDG_SESSION_DESKTOP") == "gamescope"
    )
    # Note: STEAM_MULTIPLE_XWAYLANDS is steam mode specific and is
    # documented to be a legacy env var.
    is_steammode: bool = (
        is_gamescope_session and os.environ.get("STEAM_MULTIPLE_XWAYLANDS") == "1"
    )

    if not command:
        err: str = f"Command list is empty or None: {command}"
        raise ValueError(err)

    # For winetricks, change directory to $PROTONPATH/protonfixes
    if os.environ.get("EXE", "").endswith("winetricks"):
        cwd = f"{os.environ['PROTONPATH']}/protonfixes"
    else:
        cwd = Path.cwd()

    prctl = CDLL(libc).prctl
    prctl.restype = c_int
    prctl.argtypes = [
        c_int,
        c_ulong,
        c_ulong,
        c_ulong,
        c_ulong,
    ]
    prctl_ret = prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0, 0)
    log.debug("prctl exited with status: %s", prctl_ret)

    with Popen(command, start_new_session=True, cwd=cwd) as proc:
        ret = run_in_steammode(proc) if is_steammode else proc.wait()
        log.debug("Child %s exited with wait status: %s", proc.pid, ret)

    return ret


def umu_run(args: Namespace | tuple[str, list[str]]) -> int:
    """Prepare and run an executable within the Steam Runtime.

    The executable will typically be run through Proton, unless configured
    otherwise. Will additionally download or auto update an existing Steam
    Runtime version 2 (e.g., soldier, sniper) to be installed in
    $XDG_DATA_HOME/umu or $HOME/.local/share/umu when invoked.

    See umu(1) for details on other configuration options.
    """
    env: dict[str, str] = {
        "WINEPREFIX": "",
        "GAMEID": "",
        "PROTON_CRASH_REPORT_DIR": "/tmp/umu_crashreports",
        "PROTONPATH": "",
        "STEAM_COMPAT_APP_ID": "",
        "STEAM_COMPAT_TOOL_PATHS": "",
        "STEAM_COMPAT_LIBRARY_PATHS": "",
        "STEAM_COMPAT_MOUNTS": "",
        "STEAM_COMPAT_INSTALL_PATH": "",
        "STEAM_COMPAT_CLIENT_INSTALL_PATH": "",
        "STEAM_COMPAT_DATA_PATH": "",
        "STEAM_COMPAT_SHADER_PATH": "",
        "FONTCONFIG_PATH": "",
        "EXE": "",
        "SteamAppId": "",
        "SteamGameId": "",
        "STEAM_RUNTIME_LIBRARY_PATH": "",
        "STORE": "",
        "PROTON_VERB": "",
        "UMU_ID": "",
        "UMU_ZENITY": "",
        "UMU_NO_RUNTIME": "",
        "UMU_RUNTIME_UPDATE": "",
        "UMU_NO_PROTON": "",
    }
    opts: list[str] = []
    prereq: bool = False
    root: Traversable

    try:
        root = Path(__file__).resolve(strict=True).parent
    except NotADirectoryError:
        # Raised when within a zipapp. Try again in non-strict mode
        root = ZipPath(
            Path(__file__).resolve().parent.parent, Path(__file__).parent.name
        )

    log.info("umu-launcher version %s (%s)", __version__, sys.version)

    # Test the network environment and fail early if the user is trying
    # to run umu-run offline because an internet connection is required
    # for new setups
    try:
        log.debug("Connecting to '1.1.1.1'...")
        with socket(AF_INET, SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.connect(("1.1.1.1", 53))
        prereq = True
    except TimeoutError:  # Request to a server timed out
        if not has_umu_setup():
            err: str = (
                "umu has not been setup for the user\n"
                "An internet connection is required to setup umu"
            )
            raise RuntimeError(err)
        log.debug("Request timed out")
        prereq = True
    except OSError as e:  # No internet
        if e.errno != ENETUNREACH:
            raise
        if not has_umu_setup():
            err: str = (
                "umu has not been setup for the user\n"
                "An internet connection is required to setup umu"
            )
            raise RuntimeError(err)
        log.debug("Network is unreachable")
        prereq = True

    if not prereq:
        err: str = (
            "umu has not been setup for the user\n"
            "An internet connection is required to setup umu"
        )
        raise RuntimeError(err)

    # Opt to use the system's native CA bundle rather than certifi's
    with suppress(ModuleNotFoundError):
        import truststore

        truststore.inject_into_ssl()

    # Default to retrying requests once, while using urllib's defaults
    retries: Retry = Retry(total=NET_RETRIES, redirect=True)
    # Default to a strict 5 second timeouts throughout
    timeout: Timeout = Timeout(connect=NET_TIMEOUT, read=NET_TIMEOUT)

    with (
        ThreadPoolExecutor() as thread_pool,
        PoolManager(timeout=timeout, retries=retries) as http_pool,
    ):
        session_pools: tuple[ThreadPoolExecutor, PoolManager] = (
            thread_pool,
            http_pool,
        )
        # Setup the launcher and runtime files
        future: Future = thread_pool.submit(
            setup_umu, root, UMU_LOCAL, __runtime_version__, session_pools
        )

        if isinstance(args, Namespace):
            env, opts = set_env_toml(env, args)
        else:
            opts = args[1]  # Reference the executable options
            check_env(env, session_pools)

        UMU_LOCAL.mkdir(parents=True, exist_ok=True)

        # Prepare the prefix
        with unix_flock(f"{UMU_LOCAL}/pfx.lock"):
            setup_pfx(env["WINEPREFIX"])

        # Configure the environment
        set_env(env, args)

        # Set all environment variables
        # NOTE: `env` after this block should be read only
        for key, val in env.items():
            log.debug("%s=%s", key, val)
            os.environ[key] = val

        try:
            future.result()
        except (MaxRetryError, NewConnectionError, TimeoutErrorUrllib3, ValueError):
            if not has_umu_setup():
                err: str = (
                    "umu has not been setup for the user\n"
                    "An internet connection is required to setup umu"
                )
                raise RuntimeError(err)
            log.debug("Network is unreachable")

    # Exit if the winetricks verb is already installed to avoid reapplying it
    if env["EXE"].endswith("winetricks") and is_installed_verb(
        opts, Path(env["WINEPREFIX"])
    ):
        sys.exit(1)

    # Build the command
    command: tuple[Path | str, ...] = build_command(env, UMU_LOCAL, opts)
    log.debug("%s", command)

    # Run the command
    return run_command(command)
