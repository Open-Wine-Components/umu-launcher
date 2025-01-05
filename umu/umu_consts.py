import os
from enum import Enum
from pathlib import Path


# Copyright (c) 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010,
# 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023
# Python Software Foundation;
# Source: https://raw.githubusercontent.com/python/cpython/refs/heads/3.11/Lib/http/__init__.py
# License: https://raw.githubusercontent.com/python/cpython/refs/heads/3.11/LICENSE
class HTTPMethod(Enum):
    """HTTP methods and descriptions.

    Methods from the following RFCs are all observed:

        * RFF 9110: HTTP Semantics, obsoletes 7231, which obsoleted 2616
        * RFC 5789: PATCH Method for HTTP

    """

    CONNECT = "CONNECT"
    DELETE = "DELETE"
    GET = "GET"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"
    POST = "POST"
    PUT = "PUT"
    TRACE = "TRACE"


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
        else Path(os.environ["XDG_DATA_HOME"])
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
