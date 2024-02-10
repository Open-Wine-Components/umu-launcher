import os
from pathlib import Path
from typing import Dict, Set, Tuple
import ulwgl_pressure_vessel
from io import TextIOWrapper


def enable_pressure_vessel(env: Dict[str, str]) -> Tuple[Dict[str, str], TextIOWrapper]:
    """Enable Pressure Vessel."""
    exe_dir: str = Path(__file__).parent.as_posix()
    file: TextIOWrapper = None
    env, file = ulwgl_pressure_vessel.set_pv(env)

    if "LD_LIBRARY_PATH" in os.environ:
        os.environ.pop("LD_LIBRARY_PATH")
    if "STEAM_RUNTIME" in os.environ:
        os.environ.pop("STEAM_RUNTIME")

    # Replicates ./run or ./run-in-sniper
    env["PRESSURE_VESSEL_COPY_RUNTIME"] = "1"
    env["PRESSURE_VESSEL_GC_LEGACY_RUNTIMES"] = "1"
    # Hardcode for now
    # TODO: Read from a config file for this value
    env["PRESSURE_VESSEL_RUNTIME"] = "sniper_platform_0.20231211.70175"
    env["PRESSURE_VESSEL_RUNTIME_BASE"] = exe_dir
    env["PRESSURE_VESSEL_VARIABLE_DIR"] = exe_dir + "/var"

    return (env, file)


def enable_steam_game_drive(env: Dict[str, str]) -> Dict[str, str]:
    """Enable Steam Game Drive functionality.

    Expects STEAM_COMPAT_INSTALL_PATH to be set
    STEAM_RUNTIME_LIBRARY_PATH will not be set if the exe directory does not exist
    """
    paths: Set[str] = set()
    root: Path = Path("/")

    # Check for mount points going up toward the root
    # NOTE: Subvolumes can be mount points
    for path in Path(env["STEAM_COMPAT_INSTALL_PATH"]).parents:
        if path.is_mount() and path != root:
            if env["STEAM_COMPAT_LIBRARY_PATHS"]:
                env["STEAM_COMPAT_LIBRARY_PATHS"] = (
                    env["STEAM_COMPAT_LIBRARY_PATHS"] + ":" + path.as_posix()
                )
            else:
                env["STEAM_COMPAT_LIBRARY_PATHS"] = path.as_posix()
            break

    if "LD_LIBRARY_PATH" in os.environ:
        paths.add(Path(os.environ["LD_LIBRARY_PATH"]).as_posix())

    if env["STEAM_COMPAT_INSTALL_PATH"]:
        paths.add(env["STEAM_COMPAT_INSTALL_PATH"])

    # Hard code for now because these paths seem to be pretty standard
    # This way we avoid shelling to ldconfig
    paths.add("/usr/lib")
    paths.add("/usr/lib32")
    env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(list(paths))

    return env
