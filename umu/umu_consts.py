from enum import Enum
from pathlib import Path
from os import environ


class Color(Enum):
    """Represent the color to be applied to a string."""

    RESET = "\u001b[0m"
    INFO = "\u001b[34m"
    WARNING = "\033[33m"
    ERROR = "\033[31m"
    BOLD = "\033[1m"
    DEBUG = "\u001b[35m"


class MODE(Enum):
    """Represent the permission to apply to a file."""

    USER_RW = 0o0644
    USER_RWX = 0o0755


SIMPLE_FORMAT = f"%(levelname)s:  {Color.BOLD.value}%(message)s{Color.RESET.value}"

DEBUG_FORMAT = f"%(levelname)s [%(module)s.%(funcName)s:%(lineno)s]:{Color.BOLD.value}%(message)s{Color.RESET.value}"  # noqa: E501

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

FLATPAK_ID = environ.get("FLATPAK_ID") or ""

FLATPAK_PATH: Path = Path(environ.get("XDG_DATA_HOME"), "umu") if FLATPAK_ID else None

UMU_LOCAL: Path = FLATPAK_PATH or Path.home().joinpath(".local", "share", "umu")
