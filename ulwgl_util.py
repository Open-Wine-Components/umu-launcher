from ulwgl_consts import Color, Level
from typing import Any


def msg(msg: Any, level: Level):
    """Return a log message depending on the log level.

    The message will bolden the typeface and apply a color.
    Expects the first parameter to be a string or implement __str__
    """
    log: str = ""

    if level == Level.INFO:
        log = f"{Color.BOLD.value}{Color.INFO.value}{msg}{Color.RESET.value}"
    elif level == Level.WARNING:
        log = f"{Color.BOLD.value}{Color.WARNING.value}{msg}{Color.RESET.value}"
    elif level == Level.DEBUG:
        log = f"{Color.BOLD.value}{Color.DEBUG.value}{msg}{Color.RESET.value}"

    return log
