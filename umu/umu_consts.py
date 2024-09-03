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

# Installation path of the runtime files
# Flatpak will be detected as outlined by systemd
# See https://systemd.io/CONTAINER_INTERFACE
UMU_LOCAL: Path = (
    Path.home().joinpath(
        ".var", "app", "org.openwinecomponents.umu.umu-launcher", "data", "umu"
    )
    if os.environ.get("container") == "flatpak"  # noqa: SIM112
    else Path.home().joinpath(".local", "share", "umu")
)

# Constant defined in prctl.h
# See prctl(2) for more details
PR_SET_CHILD_SUBREAPER = 36
