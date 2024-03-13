import logging
from sys import stderr
from ulwgl_consts import SIMPLE_FORMAT, Color


class Formatter(logging.Formatter):
    """Extend the logging Formatter class to apply styles for log records."""

    def __init__(self, fmt=SIMPLE_FORMAT):
        """Apply colors to the record style for each level."""
        self.fmt = fmt
        self.formats = {
            logging.DEBUG: f"{Color.DEBUG.value}{self.fmt}",
            logging.INFO: f"{Color.INFO.value}{self.fmt}",
            logging.WARNING: f"{Color.WARNING.value}{self.fmt}",
            logging.ERROR: f"{Color.ERROR.value}{self.fmt}",
        }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        formatter: logging.Formatter = logging.Formatter(
            self.formats.get(record.levelno)
        )

        return formatter.format(record)


log: logging.Logger = logging.getLogger(__name__)

console_handler: logging.StreamHandler = logging.StreamHandler(stream=stderr)
console_handler.setFormatter(Formatter())
log.addHandler(console_handler)
log.setLevel(logging.CRITICAL + 1)
