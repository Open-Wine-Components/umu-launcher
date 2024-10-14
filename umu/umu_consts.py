import os
from pathlib import Path

CONFIG = "umu_version.json"

STEAM_COMPAT: Path = Path.home().joinpath(
    ".local", "share", "Steam", "compatibilitytools.d"
)

PROTON_VERBS = {
    "waitforexitandrun",
    "run",
    "runinprefix",
    "destroyprefix",
    "getcompatpath",
    "getnativepath",
}

XDG_DATA_HOME: Path = (
    Path(os.environ["XDG_DATA_HOME"])
    if os.environ.get("XDG_DATA_HOME")
    else Path.home().joinpath(".local", "share")
)

XDG_CACHE_HOME: Path = (
    Path(os.environ["XDG_CACHE_HOME"])
    if os.environ.get("XDG_CACHE_HOME")
    else Path.home().joinpath(".cache")
)

_HOST_XDG_DATA_HOME: str = os.environ.get(
    "HOST_XDG_DATA_HOME", os.environ["XDG_DATA_HOME"]
)

# Installation path of the runtime files that respects the XDG Base Directory
# Specification and Systemd container interface.
# See https://systemd.io/CONTAINER_INTERFACE
# See https://specifications.freedesktop.org/basedir-spec/latest/index.html#basics
# NOTE: For Flatpaks, the runtime will be installed in $HOST_XDG_DATA_HOME
# then $XDG_DATA_HOME, and will be required to update their manifests by adding
# the permission 'xdg-data/umu:create'.
# See https://github.com/Open-Wine-Components/umu-launcher/pull/229#discussion_r1799289068
UMU_LOCAL: Path = (
    Path(_HOST_XDG_DATA_HOME).joinpath("umu")
    if os.environ.get("container") == "flatpak"  # noqa: SIM112
    else XDG_DATA_HOME.joinpath("umu")
)

# Temporary directory for downloaded resources moved from tmpfs
UMU_CACHE: Path = (
    Path(os.environ["XDG_CACHE_HOME"], "umu")
    if os.environ.get("container") == "flatpak"  # noqa: SIM112
    else XDG_CACHE_HOME.joinpath("umu")
)

# Constant defined in prctl.h
# See prctl(2) for more details
PR_SET_CHILD_SUBREAPER = 36
