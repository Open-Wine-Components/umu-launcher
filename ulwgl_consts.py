from enum import Enum
from logging import INFO, WARNING, DEBUG, ERROR

SIMPLE_FORMAT = "%(levelname)s:  %(message)s"

DEBUG_FORMAT = "%(levelname)s [%(module)s.%(funcName)s:%(lineno)s]:%(message)s"


class Level(Enum):
    """Represent the Log level values for the logger module."""

    INFO = INFO
    WARNING = WARNING
    DEBUG = DEBUG
    ERROR = ERROR


class Color(Enum):
    """Represent the color to be applied to a string."""

    RESET = "\u001b[0m"
    INFO = "\u001b[34m"
    WARNING = "\033[33m"
    ERROR = "\033[31m"
    BOLD = "\033[1m"
    DEBUG = "\u001b[35m"
