#!/usr/bin/python3

import os
import sys
import threading
import time
from _ctypes import CFuncPtr
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from concurrent.futures import Future, ThreadPoolExecutor
from ctypes import CDLL, c_int, c_ulong
from errno import ENETUNREACH
from logging import DEBUG, INFO, WARNING
from pathlib import Path
from pwd import getpwuid
from re import match
from socket import AF_INET, SOCK_DGRAM, socket
from subprocess import Popen
from typing import Any

# Add client's runtime path to PYTHONPATH to find dependencies
if (this_path := Path(__file__)).is_relative_to(
    Path.home()
) and "runtime" in this_path.parent.parent.name:
    sys.path.append(str(this_path.parent.parent))
elif this_path.is_relative_to(Path.home()) and os.environ.get(
    "UMU_CLIENT_RTPATH"
):
    sys.path.append(os.environ["UMU_CLIENT_RTPATH"])

from Xlib import X, Xatom, display
from Xlib.protocol.event import AnyEvent
from Xlib.xobject.drawable import Window

from umu.umu_consts import (
    DEBUG_FORMAT,
    FLATPAK_ID,
    FLATPAK_PATH,
    PR_SET_CHILD_SUBREAPER,
    PROTON_VERBS,
    STEAM_COMPAT,
    UMU_LOCAL,
)
from umu.umu_log import CustomFormatter, console_handler, log
from umu.umu_plugins import set_env_toml
from umu.umu_proton import get_umu_proton
from umu.umu_runtime import setup_umu
from umu.umu_util import get_libc, is_installed_verb, is_winetricks_verb

AnyPath = os.PathLike | str

thread_pool: ThreadPoolExecutor = ThreadPoolExecutor()


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


def set_log() -> None:
    """Adjust the log level for the logger."""
    levels: set[str] = {"1", "warn", "debug"}

    if os.environ["UMU_LOG"] not in levels:
        return

    if os.environ["UMU_LOG"] == "1":
        # Show the envvars and command at this level
        log.setLevel(level=INFO)
    elif os.environ["UMU_LOG"] == "warn":
        log.setLevel(level=WARNING)
    elif os.environ["UMU_LOG"] == "debug":
        # Show all logs
        console_handler.setFormatter(CustomFormatter(DEBUG_FORMAT))
        log.addHandler(console_handler)
        log.setLevel(level=DEBUG)


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
    else:
        log.debug("Skipping link creation for prefix")
        log.debug("User steamuser is link: %s", steam.is_symlink())
        log.debug("User home directory is link: %s", wineuser.is_symlink())


def check_env(env: dict[str, str]) -> dict[str, str] | dict[str, Any]:
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
        log.debug("Proton version selected")
        os.environ["PROTONPATH"] = str(
            STEAM_COMPAT.joinpath(os.environ["PROTONPATH"])
        )

    # GE-Proton
    if os.environ.get("PROTONPATH") == "GE-Proton":
        log.debug("GE-Proton selected")
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
    is_createpfx: bool = is_cmd and not args[0]  # type: ignore

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
        env["PROTON_VERB"] = "waitforexitandrun"
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

    return env


def enable_steam_game_drive(env: dict[str, str]) -> dict[str, str]:
    """Enable Steam Game Drive functionality."""
    paths: set[str] = set()
    root: Path = Path("/")
    libc: str = get_libc()

    # All library paths that are currently supported by the container framework
    # See https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/distro-assumptions.md#filesystem-layout
    # Non-FHS filesystems should run in a FHS chroot to comply
    steamrt_paths: list[str] = [
        "/usr/lib64",
        "/usr/lib32",
        "/usr/lib",
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib/i386-linux-gnu",
    ]

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

    # When libc.so could not be found, depend on LD_LIBRARY_PATH
    # In some cases, using ldconfig to determine library paths can fail in non-
    # FHS compliant filesystems (e.g., NixOS).
    # See https://github.com/Open-Wine-Components/umu-launcher/issues/106
    if not libc:
        log.warning("libc.so could not be found")
        log.info("LD_LIBRARY_PATH=%s", os.environ.get("LD_LIBRARY_PATH") or "")
        env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(paths)
        return env

    # Set the shared library paths of the system after finding libc.so
    for rtpath in steamrt_paths:
        if not Path(rtpath).is_symlink() and Path(rtpath, libc).is_file():
            paths.add(rtpath)

    env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(paths)

    return env


def build_command(
    env: dict[str, str],
    local: Path,
    command: list[AnyPath],
    opts: list[str] = [],
) -> list[AnyPath]:
    """Build the command to be executed."""
    proton: Path = Path(env["PROTONPATH"], "proton")
    entry_point: Path = local.joinpath("umu")

    # Will run the game w/o Proton, effectively running the game as is. This
    # option is intended for debugging purposes, and is otherwise useless
    if env.get("UMU_NO_RUNTIME") == "1":
        log.warning("Runtime Platform disabled")
        command.extend(
            [
                env["EXE"],
                *opts,
            ],
        )
        return command

    if not proton.is_file():
        err: str = "The following file was not found in PROTONPATH: proton"
        raise FileNotFoundError(err)

    if env.get("UMU_NO_RUNTIME") == "pressure-vessel":
        log.warning("Using Proton without Runtime Platform")
        command.extend(
            [
                proton,
                env["PROTON_VERB"],
                env["EXE"],
                *opts,
            ],
        )
        return command

    if not entry_point.is_file():
        err: str = (
            f"Path to _v2-entry-point cannot be found in '{local}'\n"
            "Please install a Steam Runtime platform"
        )
        raise FileNotFoundError(err)

    # Configure winetricks to not be prompted for any windows
    if env.get("EXE", "").endswith("winetricks") and opts:
        # The position of arguments matter for winetricks
        # Usage: ./winetricks [options] [command|verb|path-to-verb] ...
        opts = ["-q", *opts]

    command.extend(
        [
            entry_point,
            "--verb",
            env["PROTON_VERB"],
            "--",
            proton,
            env["PROTON_VERB"],
            env["EXE"],
            *opts,
        ],
    )

    return command


def get_window_client_ids(d: display.Display, root: Window) -> list[str]:
    """Get the list of new client windows under the root window."""
    try:
        log.debug("Waiting for new child windows")
        event: AnyEvent = d.next_event()

        if event.type == X.CreateNotify:
            log.debug("Found new child windows")
            return [child.id for child in root.query_tree().children]
    except Exception as e:
        log.exception(e)

    return []


def set_steam_game_property(  # noqa: D103
    d: display.Display, window_ids: list[str], steam_assigned_layer_id: int
) -> None:
    try:
        log.debug("steam_layer: %s", steam_assigned_layer_id)
        for window_id in window_ids:
            log.debug("window_id: %s", window_id)
            try:
                window: Window = d.create_resource_object(
                    "window", int(window_id)
                )
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
    except Exception as e:
        log.exception(e)


def get_gamescope_baselayer_order(d: display.Display) -> list[int] | None:  # noqa: D103
    try:
        root: Window = d.screen().root

        # Intern the atom for GAMESCOPECTRL_BASELAYER_APPID
        atom = d.get_atom("GAMESCOPECTRL_BASELAYER_APPID")

        # Get the property value
        prop = root.get_full_property(atom, Xatom.CARDINAL)

        if prop:
            # Extract and return the value
            return prop.value  # type: ignore
        log.debug("GAMESCOPECTRL_BASELAYER_APPID property not found")
    except Exception as e:
        log.error("Error getting GAMESCOPECTRL_BASELAYER_APPID property")
        log.exception(e)

    return None


def rearrange_gamescope_baselayer_order(  # noqa
    sequence: list[int],
) -> tuple[list[int], int]:
    # Ensure there are exactly 4 numbers
    if len(sequence) != 4:
        err = "Unexpected number of elements in sequence"
        raise ValueError(err)

    # Rearrange the sequence
    rearranged = [sequence[0], sequence[3], sequence[1], sequence[2]]
    log.debug("Rearranging base layer sequence")
    log.debug("'%s' -> '%s'", sequence, rearranged)

    # Return the rearranged sequence and the second element
    return rearranged, rearranged[1]


def set_gamescope_baselayer_order(  # noqa
    d: display.Display, root_primary: Window, rearranged: list[int]
) -> None:
    try:
        # Intern the atom for GAMESCOPECTRL_BASELAYER_APPID
        atom = d.get_atom("GAMESCOPECTRL_BASELAYER_APPID")

        # Set the property value
        root_primary.change_property(atom, Xatom.CARDINAL, 32, rearranged)
        log.debug(
            "Successfully set GAMESCOPECTRL_BASELAYER_APPID property: %s",
            ", ".join(map(str, rearranged)),
        )
    except Exception as e:
        log.error("Error setting GAMESCOPECTRL_BASELAYER_APPID property")
        log.exception(e)


def window_setup(  # noqa
    d_primary: display.Display,
    d_secondary: display.Display,
    root_primary: Window,
    gamescope_baselayer_sequence: list[int],
    game_window_ids: list[str],
) -> None:
    if gamescope_baselayer_sequence:
        # Rearrange the sequence
        rearranged_sequence, steam_assigned_layer_id = (
            rearrange_gamescope_baselayer_order(gamescope_baselayer_sequence)
        )

        # Assign our window a STEAM_GAME id
        set_steam_game_property(
            d_secondary, game_window_ids, steam_assigned_layer_id
        )

        set_gamescope_baselayer_order(
            d_primary, root_primary, rearranged_sequence
        )


def monitor_baselayer(
    d_primary: display.Display,
    root_primary: Window,
    gamescope_baselayer_sequence: list[int],
) -> None:
    """Monitor for broken gamescope baselayer sequences."""
    atom = d_primary.get_atom("GAMESCOPECTRL_BASELAYER_APPID")
    root_primary.change_attributes(event_mask=X.PropertyChangeMask)

    log.debug("Monitoring base layers")

    while True:
        event: AnyEvent = d_primary.next_event()

        # Check if the layer sequence has changed to the broken one
        if event.type == X.PropertyNotify and event.atom == atom:
            prop = root_primary.get_full_property(atom, Xatom.CARDINAL)

            log.debug("Property value for atom '%s': %s", atom, prop.value)
            if prop.value == gamescope_baselayer_sequence:
                log.debug("Broken base layer sequence detected")
                log.debug("Rearranging base layer sequence")
                rearranged = [
                    prop.value[0],
                    prop.value[3],
                    prop.value[1],
                    prop.value[2],
                ]
                log.debug("'%s' -> '%s'", prop.value, rearranged)
                set_gamescope_baselayer_order(
                    d_primary, root_primary, rearranged
                )
                continue

        time.sleep(0.1)


def monitor_windows(
    d_secondary: display.Display,
    root_secondary: Window,
    gamescope_baselayer_sequence: list[int],
    window_client_list: list[str],
) -> None:
    """Monitor for new windows and assign them Steam's layer ID."""
    steam_assigned_layer_id: int = gamescope_baselayer_sequence[-1]

    log.debug("Monitoring windows")

    while True:
        # Check if the window sequence has changed
        current_window_list = get_window_client_ids(
            d_secondary, root_secondary
        )

        if not current_window_list:
            continue

        if current_window_list != window_client_list:
            log.debug("New windows detected")
            set_steam_game_property(
                d_secondary, current_window_list, steam_assigned_layer_id
            )


def run_command(command: list[AnyPath]) -> int:
    """Run the executable using Proton within the Steam Runtime."""
    prctl: CFuncPtr
    cwd: AnyPath
    proc: Popen
    ret: int = 0
    libc: str = get_libc()
    # Primary display of the focusable app under the gamescope session
    d_primary: display.Display | None = None
    # Display of the client application under the gamescope session
    d_secondary: display.Display | None = None
    # GAMESCOPECTRL_BASELAYER_APPID value on the primary's window
    gamescope_baselayer_sequence: list[int] | None = None
    # Root window of the primary display
    root_primary: Window
    # Root window of the client application's display
    root_secondary: Window

    if not command:
        err: str = f"Command list is empty or None: {command}"
        raise ValueError(err)

    if not libc:
        log.warning("Will not set subprocess as subreaper")

    # For winetricks, change directory to $PROTONPATH/protonfixes
    if os.environ.get("EXE", "").endswith("winetricks"):
        cwd = f"{os.environ['PROTONPATH']}/protonfixes"
    else:
        cwd = Path.cwd()

    # Create a subprocess but do not set it as subreaper
    if FLATPAK_PATH or not libc:
        proc = Popen(command, start_new_session=True, cwd=cwd)
    else:
        prctl = CDLL(libc).prctl
        prctl.restype = c_int
        prctl.argtypes = [
            c_int,
            c_ulong,
            c_ulong,
            c_ulong,
            c_ulong,
        ]
        proc = Popen(
            command,
            start_new_session=True,
            preexec_fn=lambda: prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0, 0),
            cwd=cwd,
        )

    if os.environ.get("XDG_CURRENT_DESKTOP") == "gamescope":
        # :0 is where the primary xwayland server is on the Steam Deck
        d_primary = display.Display(":0")
        root_primary = d_primary.screen().root
        gamescope_baselayer_sequence = get_gamescope_baselayer_order(d_primary)

    # Dont do window fuckery if we're not inside gamescope
    if gamescope_baselayer_sequence and not os.environ.get("EXE", "").endswith(
        "winetricks"
    ):
        d_secondary = display.Display(":1")
        root_secondary = d_secondary.screen().root
        window_client_list: list[str] = []

        root_secondary.change_attributes(event_mask=X.SubstructureNotifyMask)

        # Get new windows under the client display's window
        while not window_client_list:
            window_client_list = get_window_client_ids(
                d_secondary, root_secondary
            )

        # Setup the windows
        window_setup(
            d_primary,
            d_secondary,
            root_primary,
            gamescope_baselayer_sequence,
            window_client_list,
        )

        # Monitor for new windows
        window_thread = threading.Thread(
            target=monitor_windows,
            args=(
                d_secondary,
                root_secondary,
                gamescope_baselayer_sequence,
                window_client_list,
            ),
        )
        window_thread.daemon = True
        window_thread.start()

        # Monitor for broken baselayers
        baselayer_thread = threading.Thread(
            target=monitor_baselayer,
            args=(
                d_primary,
                root_primary,
                gamescope_baselayer_sequence,
            ),
        )
        baselayer_thread.daemon = True
        baselayer_thread.start()

    try:
        ret = proc.wait()
        log.debug("Child %s exited with wait status: %s", proc.pid, ret)
    except KeyboardInterrupt:
        raise
    finally:
        if d_primary:
            d_primary.close()
        if d_secondary:
            d_secondary.close()

    return ret


def main() -> int:  # noqa: D103
    future: Future | None = None
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
    }
    command: list[AnyPath] = []
    opts: list[str] = []
    root: Path = Path(__file__).resolve(strict=True).parent
    args: Namespace | tuple[str, list[str]] = parse_args()

    if os.geteuid() == 0:
        err: str = "This script should never be run as the root user"
        log.error(err)
        sys.exit(1)

    if "musl" in os.environ.get("LD_LIBRARY_PATH", ""):
        err: str = "This script is not designed to run on musl-based systems"
        log.error(err)
        sys.exit(1)

    if "UMU_LOG" in os.environ:
        set_log()

    log.debug("Arguments: %s", args)

    if FLATPAK_PATH and root == Path("/app/share/umu"):
        log.debug("Flatpak environment detected")
        log.debug("FLATPAK_ID: %s", FLATPAK_ID)
        log.debug("Persisting the runtime at: %s", FLATPAK_PATH)

    # Setup the launcher and runtime files
    # An internet connection is required for new setups
    try:
        with socket(AF_INET, SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.connect(("1.1.1.1", 53))
        future = thread_pool.submit(setup_umu, root, UMU_LOCAL, thread_pool)
    except TimeoutError:  # Request to a server timed out
        if not UMU_LOCAL.exists() or not any(UMU_LOCAL.iterdir()):
            err: str = (
                "umu has not been setup for the user\n"
                "An internet connection is required to setup umu"
            )
            raise RuntimeError(err)
        log.debug("Request timed out")
    except OSError as e:  # No internet
        if (
            e.errno == ENETUNREACH
            and not UMU_LOCAL.exists()
            or not any(UMU_LOCAL.iterdir())
        ):
            err: str = (
                "umu has not been setup for the user\n"
                "An internet connection is required to setup umu"
            )
            raise RuntimeError(err)
        if e.errno != ENETUNREACH:
            raise
        log.debug("Network is unreachable")

    # Check environment
    if isinstance(args, Namespace):
        env, opts = set_env_toml(env, args)
    else:
        opts = args[1]  # Reference the executable options
        check_env(env)

    # Prepare the prefix
    setup_pfx(env["WINEPREFIX"])

    # Configure the environment
    set_env(env, args)

    # Set all environment variables
    # NOTE: `env` after this block should be read only
    for key, val in env.items():
        log.info("%s=%s", key, val)
        os.environ[key] = val

    if future:
        future.result()
    thread_pool.shutdown()

    # Exit if the winetricks verb is already installed to avoid reapplying it
    if env["EXE"].endswith("winetricks") and is_installed_verb(
        opts, Path(env["WINEPREFIX"])
    ):
        sys.exit(1)

    # Build the command
    build_command(env, UMU_LOCAL, command, opts)
    log.debug("%s", command)

    # Run the command
    return run_command(command)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("Keyboard Interrupt")
    except SystemExit as e:
        if e.code:
            sys.exit(e.code)
    except BaseException as e:
        log.exception(e)
    finally:
        UMU_LOCAL.joinpath(".ref").unlink(
            missing_ok=True
        )  # Cleanup .ref file on every exit
