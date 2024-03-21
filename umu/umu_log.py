import logging
from sys import stderr
from umu_consts import SIMPLE_FORMAT, Color


class CustomLogger(logging.Logger):  # noqa: D101
    def __init__(self, log: logging.Logger) -> None:  # noqa: D107
        super().__init__(log.name, log.getEffectiveLevel())

    def console(self, msg: str) -> None:
        """Display non-debug-related statements to the console.

        Intended to be used to notify umu setup progress state
        """
        print(f"{Color.BOLD.value}{msg}{Color.RESET.value}", file=stderr)


class CustomFormatter(logging.Formatter):  # noqa: D101
    def __init__(self, fmt: str = SIMPLE_FORMAT) -> None:
        """Apply colors to the record style for each level."""
        self._fmt = fmt
        self._formats = {
            logging.DEBUG: f"{Color.DEBUG.value}{self._fmt}",
            logging.INFO: f"{Color.INFO.value}{self._fmt}",
            logging.WARNING: f"{Color.WARNING.value}{self._fmt}",
            logging.ERROR: f"{Color.ERROR.value}{self._fmt}",
        }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        formatter: logging.Formatter = logging.Formatter(
            self._formats.get(record.levelno)
        )

        return formatter.format(record)


log: CustomLogger = CustomLogger(logging.getLogger(__name__))

console_handler: logging.StreamHandler = logging.StreamHandler(stream=stderr)
console_handler.setFormatter(CustomFormatter())
log.addHandler(console_handler)
