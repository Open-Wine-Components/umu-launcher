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

CONFIG = "ULWGL_VERSION.json"

ULWGL_LOCAL: Path = Path.home().joinpath(".local", "share", "ULWGL")

ULWGL_CACHE: Path = Path.home().joinpath(".cache", "ULWGL")

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
