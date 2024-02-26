from ulwgl_consts import Color, Level
from typing import Any
from os import getuid
from pathlib import Path
from pwd import struct_passwd, getpwuid


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


class UnixUser:
    """Represents the User of the system as determined by the password database rather than environment variables or file system paths."""

    def __init__(self):
        """Immutable properties of the user determined by the password database that's derived from the real user id."""
        uid: int = getuid()
        entry: struct_passwd = getpwuid(uid)
        # Immutable properties, hence no setters
        self.name: str = entry.pw_name
        self.puid: str = entry.pw_uid  # Should be equivalent to the value from getuid
        self.dir: str = entry.pw_dir
        self.is_user: bool = self.puid == uid

    def get_home_dir(self) -> Path:
        """User home directory as determined by the password database that's derived from the current process's real user id."""
        return Path(self.dir).as_posix()

    def get_user(self) -> str:
        """User (login name) as determined by the password database that's derived from the current process's real user id."""
        return self.name

    def get_puid(self) -> int:
        """Numerical user ID as determined by the password database that's derived from the current process's real user id."""
        return self.puid

    def is_user(self, uid: int) -> bool:
        """Compare the UID passed in to this instance."""
        return uid == self.puid
