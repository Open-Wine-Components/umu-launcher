import gamelauncher_util
import os


def enable_steam_game_drive(env):
    """Enable Steam Game Drive functionality."""
    paths = ""

    env["STEAM_COMPAT_LIBRARY_PATHS"] = gamelauncher_util.get_steam_compat_install(
        env["STEAM_COMPAT_INSTALL_PATH"]
    )

    if "LD_LIBRARY_PATH" in os.environ:
        paths.append(os.environ["LD_LIBRARY_PATH"])
    paths.append(env["STEAM_COMPAT_INSTALL_PATH"])
    paths.append(gamelauncher_util.get_steam_compat_lib())

    env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(paths)

    return paths
