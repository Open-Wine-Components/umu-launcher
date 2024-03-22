#!/usr/bin/env python3

import os
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path
from typing import Dict, Any, List, Set, Union, Tuple
from umu_plugins import enable_steam_game_drive, set_env_toml, enable_reaper
from re import match
from subprocess import run
from umu_dl_util import get_umu_proton
from umu_consts import PROTON_VERBS, DEBUG_FORMAT, STEAM_COMPAT, UMU_LOCAL
from umu_util import setup_umu
from umu_log import log, console_handler, CustomFormatter
from umu_util import UnixUser
from logging import INFO, WARNING, DEBUG
from errno import ENETUNREACH


def parse_args() -> Union[Namespace, Tuple[str, List[str]]]:  # noqa: D103
    opt_args: Set[str] = {"--help", "-h", "--config"}
    parser: ArgumentParser = ArgumentParser(
        description="Unified Linux Wine Game Launcher",
        epilog="See umu(1) for more info and examples.",
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument("--config", help="path to TOML file (requires Python 3.11+)")

    if not sys.argv[1:]:
        err: str = (
            "Please see project README.md for more info and examples.\n"
            "https://github.com/Open-Wine-Components/umu-launcher"
        )
        parser.print_help(sys.stderr)
        raise SystemExit(err)

    if sys.argv[1:][0] in opt_args:
        return parser.parse_args(sys.argv[1:])

    if sys.argv[1] in PROTON_VERBS:
        if "PROTON_VERB" not in os.environ:
            os.environ["PROTON_VERB"] = sys.argv[1]
        sys.argv.pop(1)

    return sys.argv[1], sys.argv[2:]


def set_log() -> None:
    """Adjust the log level for the logger."""
    levels: Set[str] = {"1", "warn", "debug"}

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

    os.environ.pop("UMU_LOG")


def setup_pfx(path: str) -> None:
    """Create a symlink to the WINE prefix and tracked_files file."""
    pfx: Path = Path(path).joinpath("pfx").expanduser()
    steam: Path = Path(path).expanduser().joinpath("drive_c", "users", "steamuser")
    user: UnixUser = UnixUser()
    wineuser: Path = (
        Path(path).expanduser().joinpath("drive_c", "users", user.get_user())
    )

    if pfx.is_symlink():
        pfx.unlink()

    if not pfx.is_dir():
        pfx.symlink_to(Path(path).expanduser())

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
        steam.symlink_to(user.get_user())
    elif not wineuser.exists() and not wineuser.is_symlink() and steam.is_dir():
        wineuser.unlink(missing_ok=True)
        wineuser.symlink_to("steamuser")
    else:
        log.debug("Skipping link creation for prefix")
        log.debug("User steamuser directory exists: %s", steam)
        log.debug("User home directory exists: %s", wineuser)


def check_env(
    env: Dict[str, str], toml: Dict[str, Any] = None
) -> Union[Dict[str, str], Dict[str, Any]]:
    """Before executing a game, check for environment variables and set them.

    GAMEID is strictly required
    """
    if "GAMEID" not in os.environ:
        err: str = "Environment variable not set: GAMEID"
        raise ValueError(err)
    env["GAMEID"] = os.environ["GAMEID"]

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
    # Ensure a string is passed instead of a path
    # Since shells auto expand paths, pathlib will destroy the STEAM_COMPAT
    # stem when it encounters a separator
    if (
        os.environ.get("PROTONPATH")
        and Path(f"{STEAM_COMPAT}/" + os.environ.get("PROTONPATH")).is_dir()
    ):
        log.debug("Proton version selected")
        os.environ["PROTONPATH"] = STEAM_COMPAT.joinpath(
            os.environ["PROTONPATH"]
        ).as_posix()

    # GE-Proton
    if os.environ.get("PROTONPATH") and os.environ.get("PROTONPATH") == "GE-Proton":
        log.debug("GE-Proton selected")
        get_umu_proton(env)

    if "PROTONPATH" not in os.environ:
        os.environ["PROTONPATH"] = ""
        get_umu_proton(env)

    env["PROTONPATH"] = os.environ["PROTONPATH"]

    # If download fails/doesn't exist in the system, raise an error
    if not os.environ["PROTONPATH"]:
        err: str = (
            "Download failed\n"
            "umu-Proton could not be found in cache or compatibilitytools.d\n"
            "Please set $PROTONPATH or visit https://github.com/Open-Wine-Components/umu-Proton/releases"
        )
        raise FileNotFoundError(err)

    return env


def set_env(
    env: Dict[str, str], args: Union[Namespace, Tuple[str, List[str]]]
) -> Dict[str, str]:
    """Set various environment variables for the Steam RT.

    Filesystem paths will be formatted and expanded as POSIX
    """
    # PROTON_VERB
    # For invalid Proton verbs, just assign the waitforexitandrun
    if "PROTON_VERB" in os.environ and os.environ["PROTON_VERB"] in PROTON_VERBS:
        env["PROTON_VERB"] = os.environ["PROTON_VERB"]
    else:
        env["PROTON_VERB"] = "waitforexitandrun"

    # EXE
    # Empty string for EXE will be used to create a prefix
    if isinstance(args, tuple) and isinstance(args[0], str) and not args[0]:
        env["EXE"] = ""
        env["STEAM_COMPAT_INSTALL_PATH"] = ""
        env["PROTON_VERB"] = "waitforexitandrun"
    elif isinstance(args, tuple):
        env["EXE"] = Path(args[0]).expanduser().as_posix()
        env["STEAM_COMPAT_INSTALL_PATH"] = Path(env["EXE"]).parent.as_posix()
    else:
        # Config branch
        env["EXE"] = Path(env["EXE"]).expanduser().as_posix()
        env["STEAM_COMPAT_INSTALL_PATH"] = Path(env["EXE"]).parent.as_posix()

    if "STORE" in os.environ:
        env["STORE"] = os.environ["STORE"]

    # UMU_ID
    env["UMU_ID"] = env["GAMEID"]
    env["ULWGL_ID"] = env["UMU_ID"]  # Set ULWGL_ID for compatibility
    env["STEAM_COMPAT_APP_ID"] = "0"

    if match(r"^umu-[\d\w]+$", env["UMU_ID"]):
        env["STEAM_COMPAT_APP_ID"] = env["UMU_ID"][env["UMU_ID"].find("-") + 1 :]
    env["SteamAppId"] = env["STEAM_COMPAT_APP_ID"]
    env["SteamGameId"] = env["SteamAppId"]

    # PATHS
    env["WINEPREFIX"] = Path(env["WINEPREFIX"]).expanduser().as_posix()
    env["PROTONPATH"] = Path(env["PROTONPATH"]).expanduser().as_posix()
    env["STEAM_COMPAT_DATA_PATH"] = env["WINEPREFIX"]
    env["STEAM_COMPAT_SHADER_PATH"] = env["STEAM_COMPAT_DATA_PATH"] + "/shadercache"
    env["STEAM_COMPAT_TOOL_PATHS"] = env["PROTONPATH"] + ":" + UMU_LOCAL.as_posix()
    env["STEAM_COMPAT_MOUNTS"] = env["STEAM_COMPAT_TOOL_PATHS"]

    return env


def build_command(
    env: Dict[str, str], local: Path, command: List[str], opts: List[str] = None
) -> List[str]:
    """Build the command to be executed."""
    verb: str = env["PROTON_VERB"]

    # Raise an error if the _v2-entry-point cannot be found
    if not local.joinpath("umu").is_file():
        home: str = Path.home().as_posix()
        dir: str = Path(__file__).parent.as_posix()
        msg: str = (
            "Path to _v2-entry-point cannot be found in: "
            f"{home}/.local/share or {dir}\n"
            "Please install a Steam Runtime platform"
        )
        raise FileNotFoundError(msg)

    if not Path(env.get("PROTONPATH")).joinpath("proton").is_file():
        err: str = "The following file was not found in PROTONPATH: proton"
        raise FileNotFoundError(err)

    enable_reaper(env, command, local)

    command.extend([local.joinpath("umu").as_posix(), "--verb", verb, "--"])
    command.extend(
        [
            Path(env.get("PROTONPATH")).joinpath("proton").as_posix(),
            verb,
            env.get("EXE"),
        ]
    )

    if opts:
        command.extend([*opts])

    return command


def main() -> int:  # noqa: D103
    env: Dict[str, str] = {
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
    }
    command: List[str] = []
    opts: List[str] = None
    # Expected files in this dir: pressure vessel, launcher files, runner,
    # config, reaper
    root: Path = Path(__file__).resolve().parent
    # Expects this dir to be in sync with root
    # On update, files will be selectively updated
    args: Union[Namespace, Tuple[str, List[str]]] = parse_args()

    if "musl" in os.environ.get("LD_LIBRARY_PATH", ""):
        err: str = "This script is not designed to run on musl-based systems"
        raise SystemExit(err)

    if "UMU_LOG" in os.environ:
        set_log()

    log.debug("Arguments: %s", args)

    # Setup the launcher and runtime files
    # An internet connection is required for new setups
    try:
        setup_umu(root, UMU_LOCAL)
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

    # Game drive
    enable_steam_game_drive(env)

    # Set all environment variables
    # NOTE: `env` after this block should be read only
    for key, val in env.items():
        log.info("%s=%s", key, val)
        os.environ[key] = val

    # Run
    build_command(env, UMU_LOCAL, command, opts)
    log.debug(command)

    return run(command).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("Keyboard Interrupt")
        sys.exit(1)
    except SystemExit as e:
        if e.code != 0:
            raise Exception(e)
    except Exception:
        log.exception("Exception")
        sys.exit(1)
    finally:
        UMU_LOCAL.joinpath(".ref").unlink(
            missing_ok=True
        )  # Cleanup .ref file on every exit
