import logging
from sys import stderr
from ulwgl_consts import SIMPLE_FORMAT, DEBUG_FORMAT

simple_formatter = logging.Formatter(SIMPLE_FORMAT)
debug_formatter = logging.Formatter(DEBUG_FORMAT)

log = logging.getLogger(__name__)

console_handler = logging.StreamHandler(stream=stderr)
console_handler.setFormatter(simple_formatter)
log.addHandler(console_handler)
log.setLevel(logging.CRITICAL + 1)
