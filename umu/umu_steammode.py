import os
import threading
import time
from array import array
from collections.abc import MutableMapping
from contextlib import suppress
from pathlib import Path
from subprocess import Popen

from Xlib import X, Xatom, display
from Xlib.error import DisplayConnectionError
from Xlib.protocol.request import GetProperty
from Xlib.protocol.rq import Event
from Xlib.xobject.drawable import Window

from umu.umu_consts import (
    STEAM_WINDOW_ID,
    GamescopeAtom,
)
from umu.umu_log import log
from umu.umu_util import (
    xdisplay,
)


def get_window_ids(d: display.Display) -> set[str] | None:
    """Get the list of window ids under the root window for a display."""
    try:
        event: Event = d.next_event()
        if event.type == X.CreateNotify:
            return {child.id for child in d.screen().root.query_tree().children}
    except Exception as e:
        log.exception(e)

    return None


def set_steam_game_property(
    d: display.Display,
    window_ids: set[str],
    steam_assigned_appid: int,
) -> display.Display:
    """Set Steam's assigned app ID on a list of windows."""
    log.debug("Steam app ID: %s", steam_assigned_appid)
    for window_id in window_ids:
        try:
            window: Window = d.create_resource_object("window", int(window_id))
            window.change_property(
                d.get_atom(GamescopeAtom.SteamGame.value),
                Xatom.CARDINAL,
                32,
                [steam_assigned_appid],
            )
            log.debug(
                "Successfully set %s property for window ID: %s",
                GamescopeAtom.SteamGame.value,
                window_id,
            )
        except Exception as e:
            log.error(
                "Error setting %s property for window ID: %s",
                GamescopeAtom.SteamGame.value,
                window_id,
            )
            log.exception(e)

    return d


def get_gamescope_baselayer_appid(
    d: display.Display,
) -> list[int] | None:
    """Get the GAMESCOPECTRL_BASELAYER_APPID value on the primary root window."""
    try:
        root_primary: Window = d.screen().root
        # Intern the atom for GAMESCOPECTRL_BASELAYER_APPID
        atom = d.get_atom(GamescopeAtom.BaselayerAppId.value)
        # Get the property value
        prop: GetProperty | None = root_primary.get_full_property(atom, Xatom.CARDINAL)
        # For GAMESCOPECTRL_BASELAYER_APPID, the value is a u32 array
        if prop and prop.value and isinstance(prop.value, array):
            # Ignore. Converting a u32 array to a list creates a list[int]
            return prop.value.tolist()  # type: ignore
        log.debug("%s property not found", GamescopeAtom.BaselayerAppId.value)
    except Exception as e:
        log.error("Error getting %s property", GamescopeAtom.BaselayerAppId.value)
        log.exception(e)

    return None


def get_steam_appid(env: MutableMapping) -> int:
    """Get the Steam app ID from the host environment variables."""
    steam_appid: int = 0

    if path := env.get("STEAM_COMPAT_TRANSCODED_MEDIA_PATH"):
        # Suppress cases when value is not a number or empty tuple
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-1])

    if path := env.get("STEAM_COMPAT_MEDIA_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-2])

    if path := env.get("STEAM_FOSSILIZE_DUMP_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-3])

    if path := env.get("DXVK_STATE_CACHE_PATH"):
        with suppress(ValueError, IndexError):
            return int(Path(path).parts[-2])

    return steam_appid


def rearrange_gamescope_baselayer_appid(
    sequence: list[int],
) -> tuple[list[int], int] | None:
    """Rearrange the GAMESCOPECTRL_BASELAYER_APPID value retrieved from a window."""
    rearranged: list[int] = list(sequence)
    steam_appid: int = get_steam_appid(os.environ)

    log.debug("%s: %s", GamescopeAtom.BaselayerAppId.value, sequence)

    if not steam_appid:
        # Case when the app ID can't be found from environment variables
        # See https://github.com/Open-Wine-Components/umu-launcher/issues/318
        log.error(
            "Failed to acquire app ID, skipping %s rearrangement",
            GamescopeAtom.BaselayerAppId.value,
        )
        return None

    try:
        rearranged.remove(steam_appid)
    except ValueError as e:
        # Case when the app ID isn't in GAMESCOPECTRL_BASELAYER_APPID
        # One case this can occur is if the client overrides Steam's env vars
        # that we get the app ID from
        log.exception(e)
        return None

    # Steam's window should be last, while assigned app id 2nd to last
    rearranged = [*rearranged[:-1], steam_appid, STEAM_WINDOW_ID]
    log.debug("Rearranging %s", GamescopeAtom.BaselayerAppId.value)
    log.debug("'%s' -> '%s'", sequence, rearranged)

    return rearranged, steam_appid


def set_gamescope_baselayer_appid(
    d: display.Display, rearranged: list[int]
) -> display.Display | None:
    """Set a new gamescope GAMESCOPECTRL_BASELAYER_APPID on the primary root window."""
    try:
        # Intern the atom for GAMESCOPECTRL_BASELAYER_APPID
        atom = d.get_atom(GamescopeAtom.BaselayerAppId.value)
        # Set the property value
        d.screen().root.change_property(atom, Xatom.CARDINAL, 32, rearranged)
        log.debug(
            "Successfully set %s property: %s",
            GamescopeAtom.BaselayerAppId.value,
            ", ".join(map(str, rearranged)),
        )
        return d
    except Exception as e:
        log.error("Error setting %s property", GamescopeAtom.BaselayerAppId.value)
        log.exception(e)

    return None


def monitor_baselayer_appid(
    d_primary: display.Display,
    gamescope_baselayer_sequence: list[int],
) -> None:
    """Monitor for broken GAMESCOPECTRL_BASELAYER_APPID values."""
    root_primary: Window = d_primary.screen().root
    rearranged_gamescope_baselayer: tuple[list[int], int] | None = None
    atom = d_primary.get_atom(GamescopeAtom.BaselayerAppId.value)
    root_primary.change_attributes(event_mask=X.PropertyChangeMask)

    log.debug(
        "Monitoring %s property for DISPLAY=%s...",
        GamescopeAtom.BaselayerAppId.value,
        d_primary.get_display_name(),
    )

    # Rearranged GAMESCOPECTRL_BASELAYER_APPID
    rearranged_gamescope_baselayer = rearrange_gamescope_baselayer_appid(
        gamescope_baselayer_sequence
    )

    # Set the rearranged GAMESCOPECTRL_BASELAYER_APPID
    if rearranged_gamescope_baselayer:
        rearranged, _ = rearranged_gamescope_baselayer
        set_gamescope_baselayer_appid(d_primary, rearranged)
        rearranged_gamescope_baselayer = None

    while True:
        event: Event = d_primary.next_event()
        prop: GetProperty | None = None

        if event.type == X.PropertyNotify and event.atom == atom:
            prop = root_primary.get_full_property(atom, Xatom.CARDINAL)

        # Check if the layer sequence has changed to the broken one
        if prop and prop.value[-1] != STEAM_WINDOW_ID:
            log.debug(
                "Broken %s property detected, will rearrange...",
                GamescopeAtom.BaselayerAppId.value,
            )
            log.debug(
                "%s has atom %s: %s",
                GamescopeAtom.BaselayerAppId.value,
                atom,
                prop.value,
            )
            rearranged_gamescope_baselayer = rearrange_gamescope_baselayer_appid(
                prop.value
            )

        if rearranged_gamescope_baselayer:
            rearranged, _ = rearranged_gamescope_baselayer
            set_gamescope_baselayer_appid(d_primary, rearranged)
            rearranged_gamescope_baselayer = None
            continue

        time.sleep(0.1)


def monitor_windows(
    d_secondary: display.Display,
) -> None:
    """Monitor for new windows for a display and assign them Steam's assigned app ID."""
    window_ids: set[str] | None = None
    steam_appid: int = get_steam_appid(os.environ)

    log.debug(
        "Waiting for new windows IDs for DISPLAY=%s...",
        d_secondary.get_display_name(),
    )

    while not window_ids:
        window_ids = get_window_ids(d_secondary)

    set_steam_game_property(d_secondary, window_ids, steam_appid)

    log.debug(
        "Monitoring for new window IDs for DISPLAY=%s...",
        d_secondary.get_display_name(),
    )

    # Check if the window sequence has changed
    while True:
        current_window_ids: set[str] | None = get_window_ids(d_secondary)

        if not current_window_ids:
            continue

        if diff := current_window_ids.difference(window_ids):
            log.debug("New window IDs detected: %s", window_ids)
            log.debug("Current tracked windows IDs: %s", current_window_ids)
            log.debug("Window IDs set difference: %s", diff)
            window_ids |= diff
            set_steam_game_property(d_secondary, diff, steam_appid)


def run_in_steammode(proc: Popen) -> int:
    """Set properties on gamescope windows when running in steam mode.

    Currently, Flatpak apps that use umu as their runtime will not have their
    game window brought to the foreground due to the base layer being out of
    order.

    See https://github.com/ValveSoftware/gamescope/issues/1341
    """
    # GAMESCOPECTRL_BASELAYER_APPID value on the primary's window
    gamescope_baselayer_sequence: list[int] | None = None

    # Currently, steamos creates two xwayland servers at :0 and :1
    # Despite the socket for display :0 being hidden at /tmp/.x11-unix in
    # in the Flatpak, it is still possible to connect to it.
    # TODO: Find a robust way to get gamescope displays both in a container
    # and outside a container
    try:
        with xdisplay(":0") as d_primary, xdisplay(":1") as d_secondary:
            gamescope_baselayer_sequence = get_gamescope_baselayer_appid(d_primary)
            # Dont do window fuckery if we're not inside gamescope
            if (
                gamescope_baselayer_sequence
                and os.environ.get("PROTON_VERB") == "waitforexitandrun"
            ):
                d_secondary.screen().root.change_attributes(
                    event_mask=X.SubstructureNotifyMask
                )

                # Monitor for new windows for the DISPLAY associated with game
                window_thread = threading.Thread(
                    target=monitor_windows, args=(d_secondary,)
                )
                window_thread.daemon = True
                window_thread.start()

                # Monitor for broken GAMESCOPECTRL_BASELAYER_APPID
                baselayer_thread = threading.Thread(
                    target=monitor_baselayer_appid,
                    args=(d_primary, gamescope_baselayer_sequence),
                )
                baselayer_thread.daemon = True
                baselayer_thread.start()
            return proc.wait()
    except DisplayConnectionError as e:
        # Case where steamos changed its display outputs as we're currently
        # assuming connecting to :0 and :1 is stable
        log.exception(e)

    return proc.wait()
