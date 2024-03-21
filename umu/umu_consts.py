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


SIMPLE_FORMAT = f"%(levelname)s:  {Color.BOLD.value}%(message)s{Color.RESET.value}"

DEBUG_FORMAT = f"%(levelname)s [%(module)s.%(funcName)s:%(lineno)s]:{Color.BOLD.value}%(message)s{Color.RESET.value}"  # noqa: E501

CONFIG = "umu_version.json"

UMU_LOCAL: Path = Path.home().joinpath(".local", "share", "umu")

UMU_CACHE: Path = Path.home().joinpath(".cache", "umu")

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
