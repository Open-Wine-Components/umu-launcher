from enum import Enum


class Color(Enum):
    """Represent the color to be applied to a string."""

    RESET = "\u001b[0m"
    INFO = "\u001b[34m"
    WARNING = "\033[33m"
    ERROR = "\033[31m"
    BOLD = "\033[1m"
    DEBUG = "\u001b[35m"


SIMPLE_FORMAT = f"%(levelname)s:  {Color.BOLD.value}%(message)s{Color.RESET.value}"

DEBUG_FORMAT = f"%(levelname)s [%(module)s.%(funcName)s:%(lineno)s]:{Color.BOLD.value}%(message)s{Color.RESET.value}"

CONFIG = "ULWGL_VERSION.json"

PROTON_VERBS = {
    "waitforexitandrun",
    "run",
    "runinprefix",
    "destroyprefix",
    "getcompatpath",
    "getnativepath",
}

USAGE = """
example usage:
  GAMEID= ulwgl-run /home/foo/example.exe
  WINEPREFIX= GAMEID= ulwgl-run /home/foo/example.exe
  WINEPREFIX= GAMEID= PROTONPATH= ulwgl-run /home/foo/example.exe
  WINEPREFIX= GAMEID= PROTONPATH= ulwgl-run /home/foo/example.exe -opengl
  WINEPREFIX= GAMEID= PROTONPATH= ulwgl-run ""
  WINEPREFIX= GAMEID= PROTONPATH= PROTON_VERB= ulwgl-run /home/foo/example.exe
  WINEPREFIX= GAMEID= PROTONPATH= STORE= ulwgl-run /home/foo/example.exe
  ULWGL_LOG= GAMEID= ulwgl-run /home/foo/example.exe
  ulwgl-run --config /home/foo/example.toml
"""
