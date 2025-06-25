import os
import re
import sys
from _ctypes import CFuncPtr
from argparse import Namespace
from collections.abc import MutableMapping
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from ctypes import CDLL, c_int, c_ulong
from errno import ENETUNREACH
from itertools import chain
from pathlib import Path
from pwd import getpwuid
from re import match
from secrets import token_hex
from socket import AF_INET, SOCK_DGRAM, socket
from subprocess import Popen
from typing import Any

from urllib3 import PoolManager, Retry
from urllib3.exceptions import MaxRetryError, NewConnectionError
from urllib3.exceptions import TimeoutError as TimeoutErrorUrllib3
from urllib3.util import Timeout

from umu import __runtime_versions__, __version__
from umu.umu_consts import (
    PR_SET_CHILD_SUBREAPER,
    PROTON_VERBS,
    STEAM_COMPAT,
    UMU_LOCAL,
    FileLock,
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
)

NET_TIMEOUT = 5.0

NET_RETRIES = 1

RuntimeVersion = tuple[str, str, str]


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
        log.info("No GAMEID set, using umu-default")
        os.environ["GAMEID"] = "umu-default"

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

    # Proton Version
    path: Path = STEAM_COMPAT.joinpath(os.environ.get("PROTONPATH", ""))
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

    env["STEAM_COMPAT_INSTALL_PATH"] = os.environ.get("STEAM_COMPAT_INSTALL_PATH", "")

    # EXE
    if is_createpfx:
        env["EXE"] = ""
        env["STEAM_COMPAT_INSTALL_PATH"] = ""
    elif is_winetricks:
        # Make an absolute path to winetricks within GE-Proton or UMU-Proton.
        # The launcher will change to the winetricks parent directory before
        # creating the subprocess
        exe: Path = Path(protonpath, "protonfixes", "winetricks")
        # Handle older protons before winetricks was added to the PATH
        env["EXE"] = str(exe.resolve(strict=True)) if exe.is_file() else "winetricks"
        args = (env["EXE"], args[1])  # type: ignore
    elif is_cmd:
        try:
            # Ensure executable path is absolute, otherwise Proton will fail
            # when creating the subprocess.
            # e.g., Games/umu/umu-0 -> $HOME/Games/umu/umu-0
            exe: Path = Path(args[0]).expanduser().resolve(strict=True)  # type: ignore
            env["EXE"] = str(exe)
            if not env["STEAM_COMPAT_INSTALL_PATH"]:
                env["STEAM_COMPAT_INSTALL_PATH"] = str(exe.parent)
        except FileNotFoundError:
            # Assume that the executable will be inside prefix or container
            env["EXE"] = args[0]  # type: ignore
            log.warning("Executable not found: %s", env["EXE"])
        env["STORE"] = os.environ.get("STORE", "")
    else:  # Configuration file usage
        exe: Path = Path(env["EXE"]).expanduser()
        env["EXE"] = str(exe)
        env["STEAM_COMPAT_INSTALL_PATH"] = str(exe.parent)
        env["STORE"] = env.get("STORE", "")

    # UMU_ID
    env["UMU_ID"] = env["GAMEID"]
    env["STEAM_COMPAT_APP_ID"] = "0"
    env["UMU_STEAM_GAME_ID"] = os.environ.get("SteamGameId", "")  # noqa: SIM112

    # Steam Application ID
    if match(r"^umu-[\d\w]+$", env["UMU_ID"]):
        env["STEAM_COMPAT_APP_ID"] = env["UMU_ID"][env["UMU_ID"].find("-") + 1 :]
    env["SteamAppId"] = env["STEAM_COMPAT_APP_ID"]
    env["SteamGameId"] = env["SteamAppId"]
    env["UMU_INVOCATION_ID"] = token_hex(16)

    # PATHS
    env["WINEPREFIX"] = str(pfx)
    env["PROTONPATH"] = str(protonpath)
    env["STEAM_COMPAT_DATA_PATH"] = env["WINEPREFIX"]
    env["STEAM_COMPAT_SHADER_PATH"] = f"{env['STEAM_COMPAT_DATA_PATH']}/shadercache"
    env["STEAM_COMPAT_TOOL_PATHS"] = (
        f"{env['PROTONPATH']}:{UMU_LOCAL}/{os.environ['RUNTIMEPATH']}"
    )
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
    env["RUNTIMEPATH"] = f"{UMU_LOCAL}/{os.environ['RUNTIMEPATH']}"

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
    reaper: Path = local.joinpath("reaper")
    appId: int = get_steam_appid(env)

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
            reaper,
            "SteamLaunch",
            "AppId=" + str(appId),
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
        reaper,
        "SteamLaunch",
        "AppId=" + str(appId),
        "--",
        shim,
        proton,
        env["PROTON_VERB"],
        env["EXE"],
        *opts,
    )


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

    with suppress(ValueError):
        return int(env.get("UMU_STEAM_GAME_ID", "")) >> 32

    return steam_appid


def run_command(command: tuple[Path | str, ...]) -> int:
    """Run the executable using Proton within the Steam Runtime."""
    prctl: CFuncPtr
    cwd: Path | str
    proc: Popen
    ret: int = 0
    prctl_ret: int = 0
    libc: str = get_libc()

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
        log.debug("Child %s exited with wait status: %s", proc.pid, ret)

    return ret


def resolve_umu_version(runtimes: tuple[RuntimeVersion, ...]) -> RuntimeVersion | None:
    """Resolve the required runtime of a compatibility tool."""
    version: tuple[str, str, str] | None = None

    if os.environ.get("RUNTIMEPATH") in set(chain.from_iterable(runtimes)):
        # Skip the parsing and trust the client
        log.debug("RUNTIMEPATH is codename, skipping version resolution")
        return next(
            member for member in runtimes if os.environ["RUNTIMEPATH"] in member
        )

    if not os.environ.get("PROTONPATH"):
        log.debug("PROTONPATH unset, defaulting to '%s'", runtimes[0][1])
        return runtimes[0]

    # Default to latest runtime for codenames
    if os.environ.get("PROTONPATH") in {"GE-Proton", "GE-Latest", "UMU-Latest"}:
        log.debug("PROTONPATH is codename, defaulting to '%s'", runtimes[0][1])
        return runtimes[0]

    # Default to latest runtime for native Linux executables
    if os.environ.get("UMU_NO_PROTON"):
        log.debug("UMU_NO_PROTON set, defaulting to '%s'", runtimes[0][1])
        return runtimes[0]

    # Solve the required runtime for PROTONPATH
    log.debug("PROTONPATH set, resolving its required runtime")
    path: Path = STEAM_COMPAT.joinpath(os.environ.get("PROTONPATH", ""))
    if os.environ.get("PROTONPATH") and path.is_dir():
        os.environ["PROTONPATH"] = str(STEAM_COMPAT.joinpath(os.environ["PROTONPATH"]))

    path = Path(os.environ["PROTONPATH"], "toolmanifest.vdf").resolve()
    if path.is_file():
        version = get_umu_version_from_manifest(path, runtimes)

    return version


def get_umu_version_from_manifest(
    path: Path, runtimes: tuple[RuntimeVersion, ...]
) -> RuntimeVersion | None:
    """Find the required runtime from a compatibility tool's configuration file."""
    key: str = "require_tool_appid"
    appids: set[str] = {member[2] for member in runtimes}
    appid: str = ""

    with path.open(mode="r", encoding="utf-8") as file:
        for line in file:
            if key not in line:
                continue
            if match := re.search(r'"require_tool_appid"\s+"(\d+)', line):
                appid = match.group(1)
                break

    if not appid:
        return None

    if appid not in appids:
        return None

    return next(member for member in runtimes if appid in member)


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
        "RUNTIMEPATH": "",
    }
    opts: list[str] = []
    prereq: bool = False
    version: RuntimeVersion | None = None

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

    # Resolve the runtime version for PROTONPATH
    version = resolve_umu_version(__runtime_versions__)
    if not version:
        err: str = (
            f"Failed to match '{os.environ.get('PROTONPATH')}' with a container runtime"
        )
        raise ValueError(err)
    os.environ["RUNTIMEPATH"] = version[1]

    # Opt to use the system's native CA bundle rather than certifi's
    with suppress(ModuleNotFoundError):
        # Ignore. truststore is an optional dep
        import truststore  # noqa: PLC0415

        truststore.inject_into_ssl()

    # Default to retrying requests once, while using urllib's defaults
    retries: Retry = Retry(total=NET_RETRIES, redirect=True)
    # Default to a strict 5 second timeouts throughout
    timeout: Timeout = Timeout(connect=NET_TIMEOUT, read=NET_TIMEOUT)

    with (
        ThreadPoolExecutor() as thread_pool,
        PoolManager(timeout=timeout, retries=retries) as http_pool,
    ):
        session_pools: tuple[ThreadPoolExecutor, PoolManager] = (thread_pool, http_pool)
        # Setup the launcher and runtime files
        future: Future = thread_pool.submit(
            setup_umu, UMU_LOCAL / version[1], version, session_pools
        )

        if isinstance(args, Namespace):
            env, opts = set_env_toml(env, args)
        else:
            opts = args[1]  # Reference the executable options
            check_env(env, session_pools)

        UMU_LOCAL.joinpath(version[1]).mkdir(parents=True, exist_ok=True)

        # Prepare the prefix
        with unix_flock(f"{UMU_LOCAL}/{FileLock.Prefix.value}"):
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
    command: tuple[Path | str, ...] = build_command(env, UMU_LOCAL / version[1], opts)
    log.debug("%s", command)

    # Run the command
    return run_command(command)
