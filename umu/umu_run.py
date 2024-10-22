#!/usr/bin/python3

import os
import sys
import threading
import time
import zipfile
from _ctypes import CFuncPtr
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from ctypes import CDLL, c_int, c_ulong
from errno import ENETUNREACH

try:
    from importlib.resources.abc import Traversable
except ModuleNotFoundError:
    from importlib.abc import Traversable

from logging import DEBUG, INFO, WARNING
from pathlib import Path
from pwd import getpwuid
from re import match
from socket import AF_INET, SOCK_DGRAM, gaierror, socket
from subprocess import Popen
from typing import Any

from filelock import FileLock
from Xlib import X, Xatom, display
from Xlib.error import DisplayConnectionError
from Xlib.protocol.request import GetProperty
from Xlib.protocol.rq import Event
from Xlib.xobject.drawable import Window

from umu import __version__
from umu.umu_consts import (
    PR_SET_CHILD_SUBREAPER,
    PROTON_VERBS,
    STEAM_COMPAT,
    STEAM_WINDOW_ID,
    UMU_LOCAL,
)
from umu.umu_log import CustomFormatter, console_handler, log
from umu.umu_plugins import set_env_toml
from umu.umu_proton import get_umu_proton
from umu.umu_runtime import setup_umu
from umu.umu_util import (
    get_libc,
    get_library_paths,
    is_installed_verb,
    is_winetricks_verb,
    xdisplay,
)


def parse_args() -> Namespace | tuple[str, list[str]]:  # noqa: D103
    opt_args: set[str] = {"--help", "-h", "--config"}
    parser: ArgumentParser = ArgumentParser(
        description="Unified Linux Wine Game Launcher",
        epilog=(
            "See umu(1) for more info and examples, or visit\n"
            "https://github.com/Open-Wine-Components/umu-launcher"
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument(
        "--config", help=("path to TOML file (requires Python 3.11+)")
    )
    parser.add_argument(
        "winetricks",
        help=("run winetricks verbs (requires UMU-Proton or GE-Proton)"),
        nargs="?",
        default=None,
    )

    if not sys.argv[1:]:
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Winetricks
    # Exit if no winetricks verbs were passed
    if sys.argv[1].endswith("winetricks") and not sys.argv[2:]:
        err: str = "No winetricks verb specified"
        log.error(err)
        sys.exit(1)

    # Exit if argument is not a verb
    if sys.argv[1].endswith("winetricks") and not is_winetricks_verb(
        sys.argv[2:]
    ):
        sys.exit(1)

    if sys.argv[1:][0] in opt_args:
        return parser.parse_args(sys.argv[1:])

    if sys.argv[1] in PROTON_VERBS:
        if "PROTON_VERB" not in os.environ:
            os.environ["PROTON_VERB"] = sys.argv[1]
        sys.argv.pop(1)

    return sys.argv[1], sys.argv[2:]


def setup_pfx(path: str) -> None:
    """Prepare a Proton compatible WINE prefix."""
    pfx: Path = Path(path).joinpath("pfx").expanduser()
    steam: Path = (
        Path(path).expanduser().joinpath("drive_c", "users", "steamuser")
    )
    # Login name of the user as determined by the password database (pwd)
    user: str = getpwuid(os.getuid()).pw_name
    wineuser: Path = Path(path).expanduser().joinpath("drive_c", "users", user)

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

    log.debug("steamuser in prefix is link: %s", steam.is_symlink())
    log.debug("user in prefix is link: %s", wineuser.is_symlink())


def check_env(
    env: dict[str, str], thread_pool: ThreadPoolExecutor
) -> dict[str, str] | dict[str, Any]:
    """Before executing a game, check for environment variables and set them.

    GAMEID is strictly required and the client is responsible for setting this.
    When the client only sets the GAMEID, the WINE prefix directory will be
    created as ~/Games/umu/GAMEID.
    """
    if not os.environ.get("GAMEID"):
        err: str = "Environment variable not set or is empty: GAMEID"
        raise ValueError(err)

    env["GAMEID"] = os.environ["GAMEID"]

    if os.environ.get("WINEPREFIX") == "":
        err: str = "Environment variable is empty: WINEPREFIX"
        raise ValueError(err)

    if "WINEPREFIX" not in os.environ:
        pfx: Path = Path.home().joinpath("Games", "umu", env["GAMEID"])
        pfx.mkdir(parents=True, exist_ok=True)
        os.environ["WINEPREFIX"] = str(pfx)

    if not Path(os.environ["WINEPREFIX"]).expanduser().is_dir():
        pfx: Path = Path(os.environ["WINEPREFIX"])
        pfx.mkdir(parents=True, exist_ok=True)
        os.environ["WINEPREFIX"] = str(pfx)

    env["WINEPREFIX"] = os.environ["WINEPREFIX"]

    # Proton Version
    if (
        os.environ.get("PROTONPATH")
        and Path(STEAM_COMPAT, os.environ["PROTONPATH"]).is_dir()
    ):
        os.environ["PROTONPATH"] = str(
            STEAM_COMPAT.joinpath(os.environ["PROTONPATH"])
        )

    # GE-Proton
    if os.environ.get("PROTONPATH") == "GE-Proton":
        get_umu_proton(env, thread_pool)

    if "PROTONPATH" not in os.environ:
        os.environ["PROTONPATH"] = ""
        get_umu_proton(env, thread_pool)

    env["PROTONPATH"] = os.environ["PROTONPATH"]

    # If download fails/doesn't exist in the system, raise an error
    if not os.environ["PROTONPATH"]:
        err: str = (
            "Download failed\n"
            "UMU-Proton could not be found in compatibilitytools.d\n"
            "Please set $PROTONPATH or visit https://github.com/Open-Wine-Components/umu-proton/releases"
        )
        raise FileNotFoundError(err)

    return env


def set_env(
    env: dict[str, str], args: Namespace | tuple[str, list[str]]
) -> dict[str, str]:
    """Set various environment variables for the Steam Runtime."""
    pfx: Path = Path(env["WINEPREFIX"]).expanduser().resolve(strict=True)
    protonpath: Path = (
        Path(env["PROTONPATH"]).expanduser().resolve(strict=True)
    )
    # Command execution usage
    is_cmd: bool = isinstance(args, tuple)
    # Command execution usage, but client wants to create a prefix. When an
    # empty string is the executable, Proton is expected to create the prefix
    # but will fail because the executable is not found
    is_createpfx: bool = (
        is_cmd and not args[0] or (is_cmd and args[0] == "createprefix")  # type: ignore
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
        exe: Path = Path(protonpath, "protonfixes", "winetricks").resolve(
            strict=True
        )
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
    else:  # Configuration file usage
        exe: Path = Path(env["EXE"]).expanduser()
        env["EXE"] = str(exe)
        env["STEAM_COMPAT_INSTALL_PATH"] = str(exe.parent)

    env["STORE"] = os.environ.get("STORE") or ""

    # UMU_ID
    env["UMU_ID"] = env["GAMEID"]
    env["ULWGL_ID"] = env["UMU_ID"]  # Set ULWGL_ID for compatibility
    env["STEAM_COMPAT_APP_ID"] = "0"

    if match(r"^umu-[\d\w]+$", env["UMU_ID"]):
        env["STEAM_COMPAT_APP_ID"] = env["UMU_ID"][
            env["UMU_ID"].find("-") + 1 :
        ]
    env["SteamAppId"] = env["STEAM_COMPAT_APP_ID"]
    env["SteamGameId"] = env["SteamAppId"]

    # PATHS
    env["WINEPREFIX"] = str(pfx)
    env["PROTONPATH"] = str(protonpath)
    env["STEAM_COMPAT_DATA_PATH"] = env["WINEPREFIX"]
    env["STEAM_COMPAT_SHADER_PATH"] = (
        f"{env['STEAM_COMPAT_DATA_PATH']}/shadercache"
    )
    env["STEAM_COMPAT_TOOL_PATHS"] = f"{env['PROTONPATH']}:{UMU_LOCAL}"
    env["STEAM_COMPAT_MOUNTS"] = env["STEAM_COMPAT_TOOL_PATHS"]

    # Zenity
    env["UMU_ZENITY"] = os.environ.get("UMU_ZENITY") or ""

    # Game drive
    enable_steam_game_drive(env)

    # Winetricks
    if env.get("EXE", "").endswith("winetricks"):
        env["WINETRICKS_SUPER_QUIET"] = (
            "" if os.environ.get("UMU_LOG") == "debug" else "1"
        )

    # Runtime
    env["UMU_NO_RUNTIME"] = os.environ.get("UMU_NO_RUNTIME") or ""
    env["UMU_RUNTIME_UPDATE"] = os.environ.get("UMU_RUNTIME_UPDATE") or ""

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

    # Will run the game w/o Proton, effectively running the game as is. This
    # option is intended for debugging purposes, and is otherwise useless
    if env.get("UMU_NO_RUNTIME") == "1":
        log.warning("Runtime Platform disabled")
        return env["EXE"], *opts

    if not proton.is_file():
        err: str = "The following file was not found in PROTONPATH: proton"
        raise FileNotFoundError(err)

    if env.get("UMU_NO_RUNTIME") == "pressure-vessel":
        log.warning("Using Proton without Runtime Platform")
        return proton, env["PROTON_VERB"], env["EXE"], *opts

    # Exit if the entry point is missing
    # The _v2-entry-point script and container framework tools are included in
    # the same image, so this can happen if the image failed to download
    if not entry_point.is_file():
        err: str = (
            f"_v2-entry-point (umu) cannot be found in '{local}'\n"
            "Runtime Platform missing or download incomplete"
        )
        raise FileNotFoundError(err)

    # Configure winetricks to not be prompted for any windows
    if env.get("EXE", "").endswith("winetricks") and opts:
        # The position of arguments matter for winetricks
        # Usage: ./winetricks [options] [command|verb|path-to-verb] ...
        opts = ["-q", *opts]

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


def get_window_client_ids(d: display.Display) -> set[str] | None:
    """Get the list of new client windows under the root window."""
    try:
        event: Event = d.next_event()

        if event.type == X.CreateNotify:
            return {
                child.id for child in d.screen().root.query_tree().children
            }
    except Exception as e:
        log.exception(e)

    return None


def set_steam_game_property(
    d: display.Display,
    window_ids: list[str] | set[str],
    steam_assigned_layer_id: int,
) -> None:
    """Set Steam's assigned layer ID on a list of windows."""
    log.debug("steam_layer: %s", steam_assigned_layer_id)

    for window_id in window_ids:
        try:
            window: Window = d.create_resource_object("window", int(window_id))
            window.change_property(
                d.get_atom("STEAM_GAME"),
                Xatom.CARDINAL,
                32,
                [steam_assigned_layer_id],
            )
            log.debug(
                "Successfully set STEAM_GAME property for window ID: %s",
                window_id,
            )
        except Exception as e:
            log.error(
                "Error setting STEAM_GAME property for window ID: %s",
                window_id,
            )
            log.exception(e)


def get_gamescope_baselayer_order(
    d: display.Display,
) -> list[int] | None:
    """Get the gamescope base layer seq on the primary root window."""
    try:
        root_primary: Window = d.screen().root

        # Intern the atom for GAMESCOPECTRL_BASELAYER_APPID
        atom = d.get_atom("GAMESCOPECTRL_BASELAYER_APPID")

        # Get the property value
        prop: GetProperty | None = root_primary.get_full_property(
            atom, Xatom.CARDINAL
        )

        if prop:
            # Extract and return the value
            return prop.value  # type: ignore
        log.debug("GAMESCOPECTRL_BASELAYER_APPID property not found")
    except Exception as e:
        log.error("Error getting GAMESCOPECTRL_BASELAYER_APPID property")
        log.exception(e)

    return None


def rearrange_gamescope_baselayer_order(
    sequence: list[int],
) -> tuple[list[int], int] | None:
    """Rearrange a gamescope base layer sequence retrieved from a window."""
    # Note: 'sequence' is actually an array type with unsigned integers
    rearranged: list[int] = list(sequence)
    steam_layer_id: int = get_steam_layer_id()

    log.debug("Base layer sequence: %s", sequence)

    if not steam_layer_id:
        return None

    try:
        rearranged.remove(steam_layer_id)
    except ValueError as e:
        # Case when the layer ID isn't in GAMESCOPECTRL_BASELAYER_APPID
        # One case this can occur is if the client overrides Steam's env vars
        # that we get the layer ID from
        log.exception(e)
        return None

    # Steam's window should be last, while assigned layer 2nd to last
    rearranged = [*rearranged[:-1], steam_layer_id, STEAM_WINDOW_ID]
    log.debug("Rearranging base layer sequence")
    log.debug("'%s' -> '%s'", sequence, rearranged)

    return rearranged, steam_layer_id


def set_gamescope_baselayer_order(
    d: display.Display, rearranged: list[int]
) -> None:
    """Set a new gamescope base layer seq on the primary root window."""
    try:
        # Intern the atom for GAMESCOPECTRL_BASELAYER_APPID
        atom = d.get_atom("GAMESCOPECTRL_BASELAYER_APPID")

        # Set the property value
        d.screen().root.change_property(atom, Xatom.CARDINAL, 32, rearranged)
        log.debug(
            "Successfully set GAMESCOPECTRL_BASELAYER_APPID property: %s",
            ", ".join(map(str, rearranged)),
        )
    except Exception as e:
        log.error("Error setting GAMESCOPECTRL_BASELAYER_APPID property")
        log.exception(e)


def get_steam_layer_id() -> int:
    """Get the Steam layer ID from the host environment variables."""
    steam_layer_id: int = 0

    if path := os.environ.get("STEAM_COMPAT_TRANSCODED_MEDIA_PATH"):
        # Suppress cases when value is not a number or empty tuple
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-1])

    if path := os.environ.get("STEAM_COMPAT_MEDIA_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-2])

    if path := os.environ.get("STEAM_FOSSILIZE_DUMP_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-3])

    if path := os.environ.get("DXVK_STATE_CACHE_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-2])

    return steam_layer_id


def monitor_baselayer(
    d_primary: display.Display,
    gamescope_baselayer_sequence: list[int],
) -> None:
    """Monitor for broken gamescope baselayer sequences."""
    root_primary: Window = d_primary.screen().root
    rearranged_gamescope_baselayer: tuple[list[int], int] | None = None
    atom = d_primary.get_atom("GAMESCOPECTRL_BASELAYER_APPID")
    root_primary.change_attributes(event_mask=X.PropertyChangeMask)

    log.debug(
        "Monitoring base layers under display '%s'...",
        d_primary.get_display_name(),
    )

    # Get a rearranged sequence from GAMESCOPECTRL_BASELAYER_APPID.
    rearranged_gamescope_baselayer = rearrange_gamescope_baselayer_order(
        gamescope_baselayer_sequence
    )

    # Set the rearranged sequence from GAMESCOPECTRL_BASELAYER_APPID.
    if rearranged_gamescope_baselayer:
        rearranged, _ = rearranged_gamescope_baselayer
        set_gamescope_baselayer_order(d_primary, rearranged)
        rearranged_gamescope_baselayer = None

    while True:
        event: Event = d_primary.next_event()
        prop: GetProperty | None = None

        if event.type == X.PropertyNotify and event.atom == atom:
            prop = root_primary.get_full_property(atom, Xatom.CARDINAL)

        # Check if the layer sequence has changed to the broken one
        if prop and prop.value[-1] != STEAM_WINDOW_ID:
            log.debug("Broken base layer sequence detected")
            log.debug("Property value for atom '%s': %s", atom, prop.value)
            rearranged_gamescope_baselayer = (
                rearrange_gamescope_baselayer_order(prop.value)
            )

        if rearranged_gamescope_baselayer:
            rearranged, _ = rearranged_gamescope_baselayer
            set_gamescope_baselayer_order(d_primary, rearranged)
            rearranged_gamescope_baselayer = None
            continue

        time.sleep(0.1)


def monitor_windows(
    d_secondary: display.Display,
) -> None:
    """Monitor for new windows and assign them Steam's layer ID."""
    window_ids: set[str] | None = None
    steam_assigned_layer_id: int = get_steam_layer_id()

    log.debug(
        "Waiting for windows under display '%s'...",
        d_secondary.get_display_name(),
    )

    while not window_ids:
        window_ids = get_window_client_ids(d_secondary)

    set_steam_game_property(d_secondary, window_ids, steam_assigned_layer_id)

    log.debug(
        "Monitoring for new windows under display '%s'...",
        d_secondary.get_display_name(),
    )

    # Check if the window sequence has changed
    while True:
        current_window_ids: set[str] | None = get_window_client_ids(
            d_secondary
        )

        if not current_window_ids:
            continue

        if diff := current_window_ids.difference(window_ids):
            log.debug("Seen windows: %s", window_ids)
            log.debug("Current windows: %s", current_window_ids)
            log.debug("Difference: %s", diff)
            log.debug("New windows detected")
            window_ids |= diff
            set_steam_game_property(d_secondary, diff, steam_assigned_layer_id)


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
        with (
            xdisplay(":0") as d_primary,
            xdisplay(":1") as d_secondary,
        ):
            gamescope_baselayer_sequence = get_gamescope_baselayer_order(
                d_primary
            )

            # Dont do window fuckery if we're not inside gamescope
            if (
                gamescope_baselayer_sequence
                and os.environ.get("PROTON_VERB") == "waitforexitandrun"
            ):
                # Note: If the executable is one that exists in the WINE prefix
                # or container it is possible that umu wil hang when running a
                # game within a gamescope session
                d_secondary.screen().root.change_attributes(
                    event_mask=X.SubstructureNotifyMask
                )

                # Monitor for new windows
                window_thread = threading.Thread(
                    target=monitor_windows,
                    args=(d_secondary,),
                )
                window_thread.daemon = True
                window_thread.start()

                # Monitor for broken baselayers
                baselayer_thread = threading.Thread(
                    target=monitor_baselayer,
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
        is_gamescope_session
        and os.environ.get("STEAM_MULTIPLE_XWAYLANDS") == "1"
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

    with Popen(
        command,
        start_new_session=True,
        cwd=cwd,
    ) as proc:
        ret = run_in_steammode(proc) if is_steammode else proc.wait()
        log.debug("Child %s exited with wait status: %s", proc.pid, ret)

    return ret


def main() -> int:  # noqa: D103
    args: Namespace | tuple[str, list[str]] = parse_args()
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
        "ULWGL_ID": "",
        "UMU_ZENITY": "",
        "UMU_NO_RUNTIME": "",
        "UMU_RUNTIME_UPDATE": "",
    }
    opts: list[str] = []
    prereq: bool = False
    root: Traversable

    try:
        root = Path(__file__).resolve(strict=True).parent
    except NotADirectoryError:
        # Raised when within a zipapp. Try again in non-strict mode
        root = zipfile.Path(
            Path(__file__).resolve().parent.parent, Path(__file__).parent.name
        )

    if os.geteuid() == 0:
        err: str = "This script should never be run as the root user"
        log.error(err)
        sys.exit(1)

    if "musl" in os.environ.get("LD_LIBRARY_PATH", ""):
        err: str = "This script is not designed to run on musl-based systems"
        log.error(err)
        sys.exit(1)

    # Adjust the log level for the logger
    if os.environ.get("UMU_LOG") == "1":
        log.setLevel(level=INFO)
    elif os.environ.get("UMU_LOG") == "warn":
        log.setLevel(level=WARNING)
    elif os.environ.get("UMU_LOG") == "debug":
        console_handler.setFormatter(CustomFormatter(DEBUG))
        log.addHandler(console_handler)
        log.setLevel(level=DEBUG)
        for key, val in os.environ.items():
            log.debug("%s=%s", key, val)

    log.console(f"umu-launcher version {__version__} ({sys.version})")

    with ThreadPoolExecutor() as thread_pool:
        try:
            # Test the network environment and fail early if the user is trying
            # to run umu-run offline because an internet connection is required
            # for new setups
            log.debug("Connecting to '1.1.1.1'...")
            with socket(AF_INET, SOCK_DGRAM) as sock:
                sock.settimeout(5)
                sock.connect(("1.1.1.1", 53))
            prereq = True
        except TimeoutError:  # Request to a server timed out
            if not UMU_LOCAL.exists() or not any(UMU_LOCAL.iterdir()):
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
            if not UMU_LOCAL.exists() or not any(UMU_LOCAL.iterdir()):
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

        # Setup the launcher and runtime files
        future: Future = thread_pool.submit(
            setup_umu, root, UMU_LOCAL, thread_pool
        )

        if isinstance(args, Namespace):
            env, opts = set_env_toml(env, args)
        else:
            opts = args[1]  # Reference the executable options
            check_env(env, thread_pool)

        UMU_LOCAL.mkdir(parents=True, exist_ok=True)

        # Prepare the prefix
        with FileLock(f"{UMU_LOCAL}/pfx.lock"):
            setup_pfx(env["WINEPREFIX"])

        # Configure the environment
        set_env(env, args)

        # Set all environment variables
        # NOTE: `env` after this block should be read only
        for key, val in env.items():
            log.info("%s=%s", key, val)
            os.environ[key] = val

        try:
            future.result()
        except gaierror as e:
            # Network address-related errors in the request to repo.steampowered.com
            # At this point, the user's network was reachable on launch, but
            # the network suddenly became unreliable so the request failed.
            log.exception(e)
        except OSError as e:
            # Similar situation as above, but the host was resolved yet the
            # network suddenly became unreachable in the request to repo.steampowered.com.
            if e.errno != ENETUNREACH:
                raise
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
