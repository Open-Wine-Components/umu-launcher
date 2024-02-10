import os
from io import TextIOWrapper
from typing import Dict, Tuple
from pathlib import Path
import datetime
import sys


def set_pv_paths(env: Dict[str, str]) -> Dict[str, str]:
    """Set library paths for Pressure Vessel."""
    if (
        "STEAM_RUNTIME" in os.environ
        and Path(os.environ["STEAM_RUNTIME"]).is_absolute()
        and "LD_LIBRARY_PATH" in os.environ
    ):
        paths = [
            path
            for path in os.environ.get("LD_LIBRARY_PATH").split(":")
            if _filter_ld_paths(path)
        ]
        print("Setting the environment variable: ", paths)
        env["PRESSURE_VESSEL_APP_LD_LIBRARY_PATH"] = ":".join(paths)
    elif os.environ.get("LD_LIBRARY_PATH"):
        env["PRESSURE_VESSEL_APP_LD_LIBRARY_PATH"] = os.environ.get("LD_LIBRARY_PATH")

    return env


def set_pv(env: Dict[str, str]) -> Tuple[Dict[str, str], TextIOWrapper]:
    """Prepare and configure Pressure Vessel."""
    # File handle created when enabling logs
    # This needs to be closed from a caller or on exit
    file: TextIOWrapper = None

    # Check if the executing directory is a symbolic link then silently remove it
    if Path(__file__ + "/var").is_symlink():
        Path(__file__ + "/var").unlink()

    file = set_pv_logs(env)
    set_pv_paths(env)

    return (env, file)


def set_pv_logs(env: Dict[str, str]) -> TextIOWrapper:
    """Set logs for Pressure Vessel.

    Logs are enabled via STEAM_LINUX_RUNTIME_LOG environment variable
    Logs are disabled by default unless it is set
    """
    app: str = "non-steam-game"
    log_file: str = ""
    log_dir: Path = None
    # Used for logging
    # NOTE: The file handle should be closed from a caller if enabling logs
    file: TextIOWrapper = None

    if os.environ.get("STEAM_LINUX_RUNTIME_VERBOSE"):
        env["PRESSURE_VESSEL_VERBOSE"] = "1"

    if env.get("STEAM_COMPAT_APP_ID") and env.get("SteamAppId"):
        app = env.get("STEAM_COMPAT_APP_ID") + "-" + env.get("SteamAppId")

    # When enabling logs create the log file and directory
    if os.environ.get("STEAM_LINUX_RUNTIME_LOG"):
        steamrt_log_dir = os.environ.get("STEAM_LINUX_RUNTIME_LOG_DIR")
        pv_log_dir = os.environ.get("PRESSURE_VESSEL_VARIABLE_DIR")

        # Set the appropiate log directory
        if steamrt_log_dir and Path.exists(steamrt_log_dir):
            print(f"Setting log directory to: {steamrt_log_dir}")
            log_dir = steamrt_log_dir
        elif pv_log_dir and Path.exists(pv_log_dir):
            print(f"Setting log directory to: {pv_log_dir}")
            log_dir = pv_log_dir
        else:
            log_dir: Path = Path(__file__ + "/var")
            print(f"Creating log directory: {log_dir}")
            log_dir.mkdir(parents=True, exist_ok=True)

        # Create the new log file
        print(f"Creating log file: {log_file}")
        log_file = "slr-" + app + "-t" + datetime.now().strftime("%H:%M:%S.%f")[:-3]
        Path(log_file).touch(exist_ok=True)
        Path(log_file).symlink_to(log_dir.stem + "/slr-latest.log")

        # Remove old log files
        if not os.environ.get("STEAM_LINUX_RUNTIME_KEEP_LOGS"):
            print(f"Removing old log files in directory: {log_dir}")
            for file in log_dir.glob("slr-" + app + "-*.log"):
                if file != log_file:
                    print(f"Removing file: {file}")
                    Path.unlink(file)

        # Attempt to log to stderr and stdout
        # Always log to stderr
        file = Path(log_file).open(mode="a")
        if os.environ.get("PRESSURE_VESSEL_BATCH"):
            sys.stderr: TextIOWrapper = file
        else:
            sys.stdout: TextIOWrapper = file
            sys.stderr: TextIOWrapper = file

        env["PRESSURE_VESSEL_LOG_INFO"] = "1"
        env["PRESSURE_VESSEL_LOG_WITH_TIMESTAMP"] = "1"

    return file


def _filter_ld_paths(path: str) -> bool:
    """Filter for paths that isn't the Steam RT itself or a path that doesn't start with it."""
    if not (
        os.environ.get("STEAM_RUNTIME") == path
        and path.startswith(os.environ.get("STEAM_RUNTIME"))
    ):
        return True
    return False
