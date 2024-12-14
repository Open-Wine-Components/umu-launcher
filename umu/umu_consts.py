import os
from enum import Enum
from pathlib import Path


class GamescopeAtom(Enum):
    """Represent Gamescope-specific X11 atom names."""

    SteamGame = "STEAM_GAME"
    BaselayerAppId = "GAMESCOPECTRL_BASELAYER_APPID"


CONFIG = "umu_version.json"

STEAM_COMPAT: Path = Path.home().joinpath(
    ".local", "share", "Steam", "compatibilitytools.d"
)

STEAM_WINDOW_ID: int = 769

PROTON_VERBS = {
    "waitforexitandrun",
    "run",
    "runinprefix",
    "destroyprefix",
    "getcompatpath",
    "getnativepath",
}

XDG_CACHE_HOME: Path = (
    Path(os.environ["XDG_CACHE_HOME"])
    if os.environ.get("XDG_CACHE_HOME")
    else Path.home().joinpath(".cache")
)

# Installation path of the runtime files that respects the XDG Base Directory
# Specification and Systemd container interface.
# See https://systemd.io/CONTAINER_INTERFACE
# See https://specifications.freedesktop.org/basedir-spec/latest/index.html#basics
# NOTE: For Flatpaks, the runtime will be installed in $HOST_XDG_DATA_HOME
# then $XDG_DATA_HOME as fallback, and will be required to update their
# manifests by adding the permission 'xdg-data/umu:create'.
# See https://github.com/Open-Wine-Components/umu-launcher/pull/229#discussion_r1799289068
if os.environ.get("container") == "flatpak":  # noqa: SIM112
    XDG_DATA_HOME: Path = (
        Path(os.environ["HOST_XDG_DATA_HOME"])
        if os.environ.get("HOST_XDG_DATA_HOME")
        else Path.home().joinpath(".local", "share")
    )
elif os.environ.get("SNAP"):
    XDG_DATA_HOME: Path = Path(os.environ["SNAP_REAL_HOME"])
else:
    XDG_DATA_HOME: Path = (
        Path(os.environ["XDG_DATA_HOME"])
        if os.environ.get("XDG_DATA_HOME")
        else Path.home().joinpath(".local", "share")
    )

UMU_LOCAL: Path = XDG_DATA_HOME.joinpath("umu")

# Temporary directory for downloaded resources moved from tmpfs
UMU_CACHE: Path = XDG_CACHE_HOME.joinpath("umu")

# Directory storing Proton and other compatibility tools built against the SLR
UMU_COMPAT: Path = XDG_DATA_HOME.joinpath("umu", "compatibilitytools")

# Constant defined in prctl.h
# See prctl(2) for more details
PR_SET_CHILD_SUBREAPER = 36

# sha512 digests of all umu maintainers' SSH public keys. Only relevant for
# those creating patch files.
# TODO: Add all public keys from relevant parties
UMU_SSH_PUBLIC_KEYS = {
    "df269f4c8aac484220b9e33f0cdccf1f9b6b300d7f1a184f2b1439ce4ac4f0875abef0a4612d4c7b116f204078369c35707ebb9c51fd08887ef1c7966dcb030c"
}
