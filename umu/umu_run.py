#!/usr/bin/env python3
import os
import sys
import random
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
from subprocess import Popen, run, PIPE
from typing import Any

from umu_consts import (
    DEBUG_FORMAT,
    FLATPAK_ID,
    FLATPAK_PATH,
    PR_SET_CHILD_SUBREAPER,
    PROTON_VERBS,
    STEAM_COMPAT,
    UMU_LOCAL,
)
from umu_log import CustomFormatter, console_handler, log
from umu_plugins import set_env_toml
from umu_proton import get_umu_proton
from umu_runtime import setup_umu
from umu_util import (
    get_libc,
    is_installed_verb,
    is_winetricks_verb,
)

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
            env["STEAM_COMPAT_INSTALL_PATH"] = str(exe.parent)
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
    # if FLATPAK_PATH:
    #    env["UMU_NO_RUNTIME"] = os.environ.get("UMU_NO_RUNTIME") or ""

    # FIXME: Currently, running games when using the Steam Runtime in a Flatpak
    # environment will cause the game window to not display within the SteamOS
    # gamescope session. Note, this is a workaround until the runtime is built
    # or the issue is fixed upstream.
    # See https://github.com/ValveSoftware/gamescope/issues/1341
    # if (
    #    not os.environ.get("UMU_NO_RUNTIME")
    #    and FLATPAK_PATH
    #    and os.environ.get("XDG_CURRENT_DESKTOP") == "gamescope"
    # ):
    #    log.debug("SteamOS gamescope session detected")
    #    log.debug("Disabling Pressure Vessel and container runtime")
    #    env["UMU_NO_RUNTIME"] = "pressure-vessel"

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
        env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(list(paths))
        return env

    # Set the shared library paths of the system after finding libc.so
    for rtpath in steamrt_paths:
        if not Path(rtpath).is_symlink() and Path(rtpath, libc).is_file():
            paths.add(rtpath)

    env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(list(paths))

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


def get_xwininfo_output() -> list[str]:
    # Wait for the window to be created
    max_wait_time = 30  # Maximum wait time in seconds
    wait_interval = 1  # Interval between checks in seconds
    elapsed_time = 0
    window_ids: list[str] = []

    # Get gamescope baselayer sequence after the window is created
    while elapsed_time < max_wait_time:
        result = run(
            ["/app/bin/xwininfo", "-d", ":1", "-root", "-tree"],
            text=True,
            capture_output=True,
            check=False,
        )

        # Check for errors
        if result.returncode != 0:
            log.error(
                "Error executing xwininfo command: %s", f"{result.stderr}"
            )
            return None

        # Filter and process the output
        for line in result.stdout.splitlines():
            # Wait until steamcompmgr is not the first in the list
            if line.strip().startswith("0x") and "steamcompmgr" not in line:
                break
        time.sleep(wait_interval)
        elapsed_time += wait_interval

    # Finally, add all items to the list (including steamcompmgr)
    for line in result.stdout.splitlines():
        if line.strip().startswith("0x") and "steam_app" in line:
            parts = line.split()
            if len(parts) > 0:
                window_ids.append(parts[0])

    if window_ids:
        return window_ids

    # Return None if no valid window ID is found within the maximum wait time
    return None


def set_steam_game_property(
    window_ids: list[str], steam_assigned_layer_id: str
) -> None:
    try:
        for window_id in window_ids:
            # Execute the second command with the output from the first command
            result = Popen(
                [
                    "/app/bin/xprop",
                    "-d",
                    ":1",
                    "-id",
                    window_id,
                    "-f",
                    "STEAM_GAME",
                    "32c",
                    "-set",
                    "STEAM_GAME",
                    steam_assigned_layer_id,
                ],
                stdout=PIPE,
                stderr=PIPE,
                text=True,
            )

            # Check for errors
            if result.returncode != 0:
                log.error(
                    "Error executing xprop command: %s", f"{result.stderr}"
                )
            else:
                log.debug(
                    "Successfully set STEAM_GAME property for window ID: %s",
                    window_id,
                )
    except Exception as e:
        log.exception(e)


def get_gamescope_baselayer_order() -> str:
    try:
        # Execute the command and capture the output
        result = run(
            ["/app/bin/xprop", "-d", ":0", "-root"],
            text=True,
            capture_output=True,
            check=False,
        )

        # Check for errors
        if result.returncode != 0:
            log.error("Error executing command: %s", f"{result.stderr}")
            return None

        # Filter and process the output
        for line in result.stdout.splitlines():
            if "GAMESCOPECTRL_BASELAYER_APPID" in line:
                # Extract the value after '=' and strip any whitespace
                return line.split("=")[1].strip()
    except Exception as e:
        log.exception(e)
        return None


def rearrange_gamescope_baselayer_order(sequence: str) -> tuple[str, str]:
    # Split the sequence into individual numbers
    numbers = sequence.split(", ")

    # Ensure there are exactly 4 numbers
    if len(numbers) != 4:
        err = "Unexpected number of elements in sequence"
        raise ValueError(err)

    # Rearrange the sequence
    rearranged = [numbers[0], numbers[3], numbers[1], numbers[2]]

    # Join the rearranged sequence into a string
    rearranged_sequence = ", ".join(rearranged)

    # Return the rearranged sequence and the second element
    return rearranged_sequence, rearranged[1]


def run_command(command: list[AnyPath]) -> int:
    """Run the executable using Proton within the Steam Runtime."""
    prctl: CFuncPtr
    cwd: AnyPath
    proc: Popen
    ret: int = 0
    libc: str = get_libc()

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

    # Rearrange our gamescope window order
    gamescope_baselayer_sequence = get_gamescope_baselayer_order()
    if gamescope_baselayer_sequence:
        # Rearrange the sequence
        rearranged_sequence, steam_assigned_layer_id = (
            rearrange_gamescope_baselayer_order(gamescope_baselayer_sequence)
        )
        log.info(" GAMESCOPE_LAYER_SEQUENCE_SET: %s", rearranged_sequence)
        if rearranged_sequence:
            run(
                [
                    "/app/bin/xprop",
                    "-d",
                    ":0",
                    "-root",
                    "-f",
                    "GAMESCOPECTRL_BASELAYER_APPID",
                    "32co",
                    "-set",
                    "GAMESCOPECTRL_BASELAYER_APPID",
                    rearranged_sequence,
                ],
                check=False,
            )
        # Assign our window a STEAM_GAME id
        game_window_ids = get_xwininfo_output()
        if game_window_ids:
            set_steam_game_property(game_window_ids, steam_assigned_layer_id)

    ret = proc.wait()
    log.debug("Child %s exited with wait status: %s", proc.pid, ret)

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
        "XAUTHORITY": str(Path("~/.Xauthority").expanduser()),
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
