import os
from pathlib import Path

CONFIG = "umu_version.json"

STEAM_COMPAT: Path = Path.home().joinpath(
    ".local", "share", "Steam", "compatibilitytools.d"
)

PROTON_VERBS = {
    "waitforexitandrun",
    "run",
    "runinprefix",
    "destroyprefix",
    "getcompatpath",
    "getnativepath",
}

# Flatpak will be detected as outlined by systemd
# See https://systemd.io/CONTAINER_INTERFACE
IS_FLATPAK = os.environ.get("container") == "flatpak" 
default_data_home = Path.home().joinpath(".local", "share")
flatpak_data_home = Path(os.environ.get("HOST_XDG_DATA_HOME", default_data_home))

# Installation path of the runtime files
UMU_LOCAL: Path = (
    flatpak_data_home
    if IS_FLATPAK
    else Path(os.environ.get("XDG_DATA_HOME", default_data_home))
).joinpath("umu")

# Constant defined in prctl.h
# See prctl(2) for more details
PR_SET_CHILD_SUBREAPER = 36
