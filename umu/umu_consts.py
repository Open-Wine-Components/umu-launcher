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


class FileLock(Enum):
    """Files placed with an exclusive lock via flock(2)."""

    Runtime = "umu.lock"  # UMU_RUNTIME lock
    Compat = "compatibilitytools.d.lock"  # PROTONPATH lock
    Prefix = "pfx.lock"  # WINEPREFIX lock


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

STEAM_COMPAT: Path = XDG_DATA_HOME.joinpath("Steam", "compatibilitytools.d")

# Constant defined in prctl.h
# See prctl(2) for more details
PR_SET_CHILD_SUBREAPER = 36

# Winetricks settings verbs dumped from wintricks 20240105
# Script:
# --
# import sys
# from subprocess import PIPE, Popen
#
# with (Popen(["winetricks", "settings", "list"], stdout=PIPE) as wpt,
#       Popen(["awk", "{print $1}"], stdout=PIPE, stdin=wpt.stdout) as awkp
#       ):
#         sys.stdout.write("WINETRICKS_SETTINGS_VERBS = {\n")
#         for line in awkp.stdout:
#             line = line.decode("utf-8").strip()
#             sys.stdout.write(f"    \"{line}\",\n")
#         sys.stdout.write("}\n")
# --
WINETRICKS_SETTINGS_VERBS = {
    "alldlls=builtin",
    "alldlls=default",
    "autostart_winedbg=disabled",
    "autostart_winedbg=enabled",
    "bad",
    "cfc=disabled",
    "cfc=enabled",
    "csmt=force",
    "csmt=off",
    "csmt=on",
    "fontfix",
    "fontsmooth=bgr",
    "fontsmooth=disable",
    "fontsmooth=gray",
    "fontsmooth=rgb",
    "forcemono",
    "good",
    "grabfullscreen=n",
    "grabfullscreen=y",
    "gsm=0",
    "gsm=1",
    "gsm=2",
    "gsm=3",
    "heapcheck",
    "hidewineexports=disable",
    "hidewineexports=enable",
    "hosts",
    "isolate_home",
    "macdriver=mac",
    "macdriver=x11",
    "mackeyremap=both",
    "mackeyremap=left",
    "mackeyremap=none",
    "mimeassoc=off",
    "mimeassoc=on",
    "mwo=disable",
    "mwo=enabled",
    "mwo=force",
    "native_mdac",
    "native_oleaut32",
    "nocrashdialog",
    "npm=repack",
    "nt351",
    "nt40",
    "orm=backbuffer",
    "orm=fbo",
    "psm=0",
    "psm=1",
    "psm=2",
    "psm=3",
    "remove_mono",
    "renderer=gdi",
    "renderer=gl",
    "renderer=no3d",
    "renderer=vulkan",
    "rtlm=auto",
    "rtlm=disabled",
    "rtlm=readdraw",
    "rtlm=readtex",
    "rtlm=texdraw",
    "rtlm=textex",
    "sandbox",
    "set_mididevice",
    "set_userpath",
    "shader_backend=arb",
    "shader_backend=glsl",
    "shader_backend=none",
    "sound=alsa",
    "sound=coreaudio",
    "sound=disabled",
    "sound=oss",
    "sound=pulse",
    "ssm=disabled",
    "ssm=enabled",
    "usetakefocus=n",
    "usetakefocus=y",
    "vd=1024x768",
    "vd=1280x1024",
    "vd=1440x900",
    "vd=640x480",
    "vd=800x600",
    "vd=off",
    "videomemorysize=1024",
    "videomemorysize=2048",
    "videomemorysize=512",
    "videomemorysize=default",
    "vista",
    "vsm=0",
    "vsm=1",
    "vsm=2",
    "vsm=3",
    "win10",
    "win11",
    "win20",
    "win2k3",
    "win2k8r2",
    "win2k8",
    "win2k",
    "win30",
    "win31",
    "win7",
    "win81",
    "win8",
    "win95",
    "win98",
    "windowmanagerdecorated=n",
    "windowmanagerdecorated=y",
    "windowmanagermanaged=n",
    "windowmanagermanaged=y",
    "winme",
    "winver=",
    "winxp",
}
