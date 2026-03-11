import os
import sys
from logging import Formatter, Logger, LogRecord, StreamHandler


class Color:  # noqa: D101
    ERROR = "\033[31m"  # Red
    DEBUG = "\u001b[35m"  # Purple
    INFO = "\u001b[34m"  # Blue
    WARNING = "\033[33m"  # Yellow
    CRITICAL = "\033[33m"
    BOLD = "\033[1m"
    GREY = "\033[90m"
    RESET = "\u001b[0m"


SIMPLE_FORMAT = "%(levelname)s: %(message)s"

DEBUG_FORMAT = "[%(name)s.%(module)s:%(lineno)d] %(levelname)s: %(message)s"


class CustomLogger(Logger):  # noqa: D101
    def __init__(self, name: str) -> None:  # noqa: D107
        self._custom_fmt = SIMPLE_FORMAT
        super().__init__(name)

    def set_formatter(self, level: str) -> None:  # noqa: D102
        console_handler: StreamHandler
        if level in {"1", "debug"}:  # Values for UMU_LOG
            self._custom_fmt = DEBUG_FORMAT
            self.setLevel("DEBUG")
        console_handler = StreamHandler(stream=sys.stderr)
        console_handler.setFormatter(CustomFormatter(self._custom_fmt))
        for handler in self.handlers:
            self.removeHandler(handler)
        log.addHandler(console_handler)


class CustomFormatter(Formatter):  # noqa: D101
    def format(self, record: LogRecord) -> str:  # noqa: D102
        if not os.isatty(sys.stderr.fileno()):
            return super().format(record)
        color: str
        match record.levelname:
            case "INFO":
                color = Color.INFO
            case "DEBUG":
                color = Color.DEBUG
            case "CRITICAL":
                color = Color.CRITICAL
            case "ERROR":
                color = Color.ERROR
            case "WARNING":
                color = Color.WARNING
            case "WARN":
                color = Color.WARNING
            case "FATAL":
                color = Color.WARNING
            case _:
                color = Color.BOLD
        record.levelname = f"{color}{Color.BOLD}{record.levelname}{Color.RESET}"
        return super().format(record)


log: CustomLogger = CustomLogger(__package__ or "umu")

console_handler: StreamHandler = StreamHandler(stream=sys.stderr)
console_handler.setFormatter(CustomFormatter(SIMPLE_FORMAT))
log.addHandler(console_handler)
log.setLevel("INFO")
