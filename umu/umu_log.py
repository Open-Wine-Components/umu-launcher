import sys
from logging import (
    Formatter,
    Logger,
    LogRecord,
    StreamHandler,
)

LogColor = {
    "RESET": "\u001b[0m",
    "INFO": "\u001b[34m",  # Blue
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",  # Red
    "DEBUG": "\u001b[35m",  # Purple
    "BOLD": "\033[1m",
    "GREY": "\033[90m",
}

SIMPLE_FORMAT = f"[{__package__}] %(levelname)s: %(message)s"

DEBUG_FORMAT = (
    f"[{__package__}.%(module)s:%(lineno)d] %(levelname)s: %(message)s"
)


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
        record.levelname = f"{LogColor.get(record.levelname)}{LogColor.get('BOLD')}{record.levelname}{LogColor.get('RESET')}"
        return super().format(record)


log: CustomLogger = CustomLogger(__package__ or "umu")

console_handler: StreamHandler = StreamHandler(stream=sys.stderr)
console_handler.setFormatter(CustomFormatter(SIMPLE_FORMAT))
log.addHandler(console_handler)
log.setLevel("INFO")
