from logging import (
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Formatter,
    Logger,
    LogRecord,
    StreamHandler,
    getLogger,
)
from sys import stderr

from umu_consts import SIMPLE_FORMAT, Color


class CustomLogger(Logger):  # noqa: D101
    def __init__(self, log: Logger) -> None:  # noqa: D107
        super().__init__(log.name, log.getEffectiveLevel())

    def console(self, msg: str) -> None:
        """Display non-debug-related statements to the console.

        Intended to be used to notify umu setup progress state for command
        line usage
        """
        print(f"{Color.BOLD.value}{msg}{Color.RESET.value}", file=stderr)


class CustomFormatter(Formatter):  # noqa: D101
    def __init__(self, fmt: str = SIMPLE_FORMAT) -> None:
        """Apply colors to the record style for each level."""
        self._fmt = fmt
        self._formats = {
            DEBUG: f"{Color.DEBUG.value}{self._fmt}",
            INFO: f"{Color.INFO.value}{self._fmt}",
            WARNING: f"{Color.WARNING.value}{self._fmt}",
            ERROR: f"{Color.ERROR.value}{self._fmt}",
        }

    def format(self, record: LogRecord) -> str:  # noqa: D102
        formatter: Formatter = Formatter(self._formats.get(record.levelno))

        return formatter.format(record)


log: CustomLogger = CustomLogger(getLogger(__name__))

console_handler: StreamHandler = StreamHandler(stream=stderr)
console_handler.setFormatter(CustomFormatter())
log.addHandler(console_handler)
