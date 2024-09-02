import os
from enum import Enum
from pathlib import Path


class Color(Enum):
    """Represent the color to be applied to a string."""

    RESET = "\u001b[0m"
    INFO = "\u001b[34m"
    WARNING = "\033[33m"
    ERROR = "\033[31m"
    BOLD = "\033[1m"
    DEBUG = "\u001b[35m"


SIMPLE_FORMAT = (
    f"%(levelname)s: {Color.BOLD.value}%(message)s{Color.RESET.value}"
)

DEBUG_FORMAT = f"[%(module)s] %(levelname)s: {Color.BOLD.value}%(message)s{Color.RESET.value}"  # noqa: E501

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
