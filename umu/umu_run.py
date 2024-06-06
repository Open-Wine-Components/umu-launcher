#!/usr/bin/env python3

import os
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from ctypes import CDLL, c_int, c_ulong
from errno import ENETUNREACH
from logging import DEBUG, INFO, WARNING
from pathlib import Path
from pwd import getpwuid
from re import match
from socket import AF_INET, SOCK_DGRAM, socket
from subprocess import Popen, run
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
from umu_proton import Proton, get_umu_proton
from umu_runtime import setup_umu
from umu_util import get_libc, is_installed_verb, is_winetricks_verb

THREAD_POOL: ThreadPoolExecutor = ThreadPoolExecutor()


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
        help=("run winetricks (requires UMU-Proton or GE-Proton)"),
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
        sys.argv[2:][0]
    ):
        verb: str = sys.argv[2:][0]
        err: str = f"Value is not a winetricks verb: {verb}"
        log.error(err)
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
    """Create a symlink to the WINE prefix and tracked_files file."""
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
    if (
        not wineuser.is_dir()
        and not steam.is_dir()
        and not (wineuser.is_symlink() or steam.is_symlink())
    ):
        # For new prefixes with our Proton: user -> steamuser
        steam.mkdir(parents=True)
        wineuser.unlink(missing_ok=True)
        wineuser.symlink_to("steamuser")
    elif wineuser.is_dir() and not steam.is_dir() and not steam.is_symlink():
        # When there's a user dir: steamuser -> user
        steam.unlink(missing_ok=True)
        steam.symlink_to(user)
    elif (
        not wineuser.exists() and not wineuser.is_symlink() and steam.is_dir()
    ):
        wineuser.unlink(missing_ok=True)
        wineuser.symlink_to("steamuser")
    else:
        log.debug("Skipping link creation for prefix")
        log.debug("User steamuser directory exists: %s", steam)
        log.debug("User home directory exists: %s", wineuser)


def check_env(env: set[str, str]) -> dict[str, str] | dict[str, Any]:
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
        id: str = env["GAMEID"]
        pfx: Path = Path.home().joinpath("Games", "umu", f"{id}")
        pfx.mkdir(parents=True, exist_ok=True)
        os.environ["WINEPREFIX"] = pfx.as_posix()
    if not Path(os.environ["WINEPREFIX"]).expanduser().is_dir():
        pfx: Path = Path(os.environ["WINEPREFIX"])
        pfx.mkdir(parents=True, exist_ok=True)
        os.environ["WINEPREFIX"] = pfx.as_posix()
    env["WINEPREFIX"] = os.environ["WINEPREFIX"]

    # Proton Version
    if (
        os.environ.get("PROTONPATH")
        and Path(STEAM_COMPAT, os.environ.get("PROTONPATH")).is_dir()
    ):
        log.debug("Proton version selected")
        os.environ["PROTONPATH"] = STEAM_COMPAT.joinpath(
            os.environ["PROTONPATH"]
        ).as_posix()

    # GE-Proton
    if os.environ.get("PROTONPATH") == "GE-Proton":
        log.debug("GE-Proton selected")
        get_umu_proton(env, THREAD_POOL)

    if "PROTONPATH" not in os.environ:
        os.environ["PROTONPATH"] = ""
        get_umu_proton(env, THREAD_POOL)

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
    # PROTON_VERB
    # For invalid Proton verbs, just assign the waitforexitandrun
    if os.environ.get("PROTON_VERB") in PROTON_VERBS:
        env["PROTON_VERB"] = os.environ["PROTON_VERB"]
    else:
        env["PROTON_VERB"] = "waitforexitandrun"

    # EXE
    # Empty string for EXE will be used to create a prefix
    if isinstance(args, tuple) and isinstance(args[0], str) and not args[0]:
        env["EXE"] = ""
        env["STEAM_COMPAT_INSTALL_PATH"] = ""
        env["PROTON_VERB"] = "waitforexitandrun"
    elif isinstance(args, tuple) and args[0] == "winetricks":
        # Make an absolute path to winetricks that is within our Proton, which
        # includes the dependencies bundled within the protonfix directory.
        # Fixes exit 3 status codes after applying verbs
        bin: str = (
            Path(env["PROTONPATH"], "protonfixes", "winetricks")
            .expanduser()
            .resolve(strict=True)
            .as_posix()
        )
        log.debug("EXE: %s -> %s", args[0], bin)
        args: tuple[str, list[str]] = (bin, args[1])
        env["EXE"] = bin
        env["STEAM_COMPAT_INSTALL_PATH"] = Path(env["EXE"]).parent.as_posix()
    elif isinstance(args, tuple):
        try:
            env["EXE"] = (
                Path(args[0]).expanduser().resolve(strict=True).as_posix()
            )
            env["STEAM_COMPAT_INSTALL_PATH"] = Path(
                env["EXE"]
            ).parent.as_posix()
        except FileNotFoundError:
            # Assume that the executable will be inside prefix or container
            env["EXE"] = Path(args[0]).as_posix()
            env["STEAM_COMPAT_INSTALL_PATH"] = ""
            log.warning("Executable not found: %s", env["EXE"])
    else:
        # Config branch
        env["EXE"] = Path(env["EXE"]).expanduser().as_posix()
        env["STEAM_COMPAT_INSTALL_PATH"] = Path(env["EXE"]).parent.as_posix()

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
    env["WINEPREFIX"] = (
        Path(env["WINEPREFIX"]).expanduser().resolve(strict=True).as_posix()
    )
    env["PROTONPATH"] = (
        Path(env["PROTONPATH"]).expanduser().resolve(strict=True).as_posix()
    )
    env["STEAM_COMPAT_DATA_PATH"] = env["WINEPREFIX"]
    env["STEAM_COMPAT_SHADER_PATH"] = (
        env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
    )
    env["STEAM_COMPAT_TOOL_PATHS"] = (
        env["PROTONPATH"] + ":" + UMU_LOCAL.as_posix()
    )
    env["STEAM_COMPAT_MOUNTS"] = env["STEAM_COMPAT_TOOL_PATHS"]

    # Zenity
    env["UMU_ZENITY"] = os.environ.get("UMU_ZENITY") or ""

    # Game drive
    enable_steam_game_drive(env)

    # Winetricks
    if env.get("EXE").endswith("winetricks"):
        proton: Proton = Proton(os.environ["PROTONPATH"])
        env["WINE"] = proton.wine_bin
        env["WINELOADER"] = proton.wine_bin
        env["WINESERVER"] = proton.wineserver_bin
        env["WINETRICKS_LATEST_VERSION_CHECK"] = "disabled"
        env["LD_PRELOAD"] = ""
        env["WINEDLLPATH"] = ":".join(
            [
                Path(proton.lib_dir, "wine").as_posix(),
                Path(proton.lib64_dir, "wine").as_posix(),
            ]
        )
        env["WINETRICKS_SUPER_QUIET"] = (
            "" if os.environ.get("UMU_LOG") == "debug" else "1"
        )

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
                    os.environ["STEAM_COMPAT_LIBRARY_PATHS"]
                    + ":"
                    + path.as_posix()
                )
            else:
                env["STEAM_COMPAT_LIBRARY_PATHS"] = path.as_posix()
            break

    if os.environ.get("LD_LIBRARY_PATH"):
        paths = {path for path in os.environ["LD_LIBRARY_PATH"].split(":")}

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
    # See https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/distro-assumptions.md#filesystem-layout
    for path in steamrt_paths:
        if not Path(path).is_symlink() and Path(path, libc).is_file():
            paths.add(path)
    env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(list(paths))

    return env


def build_command(
    env: dict[str, str],
    local: Path,
    command: list[str],
    opts: list[str] = None,
) -> list[str]:
    """Build the command to be executed."""
    verb: str = env["PROTON_VERB"]

    # Raise an error if the _v2-entry-point cannot be found
    if not local.joinpath("umu").is_file():
        err: str = (
            "Path to _v2-entry-point cannot be found in: "
            f"{local}\n"
            "Please install a Steam Runtime platform"
        )
        raise FileNotFoundError(err)

    if not Path(env.get("PROTONPATH")).joinpath("proton").is_file():
        err: str = "The following file was not found in PROTONPATH: proton"
        raise FileNotFoundError(err)

    # Configure winetricks to not be prompted for any windows
    if env.get("EXE").endswith("winetricks") and opts:
        # The position of arguments matter for winetricks
        # Usage: ./winetricks [options] [command|verb|path-to-verb] ...
        opts.insert(0, "-q")

    if opts:
        command.extend(
            [
                local.joinpath("umu").as_posix(),
                "--verb",
                verb,
                "--",
                Path(env.get("PROTONPATH")).joinpath("proton").as_posix(),
                verb,
                env.get("EXE"),
                *opts,
            ],
        )
        return command
    command.extend(
        [
            local.joinpath("umu").as_posix(),
            "--verb",
            verb,
            "--",
            Path(env.get("PROTONPATH")).joinpath("proton").as_posix(),
            verb,
            env.get("EXE"),
        ],
    )

    return command


def run_command(command: list[str]) -> int:
    """Run the executable using Proton within the Steam Runtime."""
    # Configure a process via libc prctl()
    # See prctl(2) for more details
    prctl: Callable[
        [c_int, c_ulong, c_ulong, c_ulong, c_ulong],
        c_int,
    ] = None
    proc: Popen = None
    ret: int = 0
    libc: str = get_libc()
    cwd: str = ""

    if not command:
        err: str = f"Command list is empty or None: {command}"
        raise ValueError(err)

    if not libc:
        log.warning("Will not set subprocess as subreaper")

    # For winetricks, change directory to $PROTONPATH/protonfixes
    if os.environ.get("EXE").endswith("winetricks"):
        cwd = Path(os.environ.get("PROTONPATH"), "protonfixes").as_posix()
    else:
        cwd = Path.cwd().as_posix()

    # Create a subprocess but do not set it as subreaper
    # Unnecessary in a Flatpak and prctl() will fail if libc could not be found
    if FLATPAK_PATH or not libc:
        return run(command, start_new_session=True, check=False).returncode

    prctl = CDLL(libc).prctl
    prctl.restype = c_int
    prctl.argtypes = [
        c_int,
        c_ulong,
        c_ulong,
        c_ulong,
        c_ulong,
    ]

    # Create a subprocess and set it as subreaper
    # When the launcher dies, the subprocess and its descendents will continue
    # to run in the background
    proc = Popen(
        command,
        start_new_session=True,
        preexec_fn=lambda: prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0, 0),
        cwd=cwd,
    )
    ret = proc.wait()
    log.debug("Child %s exited with wait status: %s", proc.pid, ret)

    return ret


def main() -> int:  # noqa: D103
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
    }
    command: list[str] = []
    opts: list[str] = []
    root: Path = Path(__file__).resolve(strict=True).parent
    future: Future = None
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
        future = THREAD_POOL.submit(setup_umu, root, UMU_LOCAL, THREAD_POOL)
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
    if isinstance(args, Namespace) and getattr(args, "config", None):
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
    THREAD_POOL.shutdown()

    # Exit if the winetricks verb is already installed to avoid reapplying it
    if env.get("EXE").endswith("winetricks") and is_installed_verb(
        opts[0], Path(env.get("WINEPREFIX"))
    ):
        pfx: str = os.environ["WINEPREFIX"]
        err: str = (
            f"winetricks verb '{opts[0]}' is already installed in '{pfx}'"
        )
        log.error(err)
        sys.exit(1)

    # Run
    build_command(env, UMU_LOCAL, command, opts)
    log.debug("%s", command)

    return run_command(command)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("Keyboard Interrupt")
    except SystemExit as e:
        if e.code:
            sys.exit(e.code)
    except BaseException:
        log.exception("BaseException")
    finally:
        UMU_LOCAL.joinpath(".ref").unlink(
            missing_ok=True
        )  # Cleanup .ref file on every exit
