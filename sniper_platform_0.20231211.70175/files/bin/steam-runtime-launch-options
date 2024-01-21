#!/bin/sh

# launch-options.sh — undo Steam Runtime environment to run launch-options.py
#
# Copyright © 2017-2022 Collabora Ltd.
#
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

set -e
set -u

main () {
    me="$(readlink -f "$0")"
    here="${me%/*}"
    me="${me##*/}"

    default_path="/usr/local/sbin:/usr/sbin:/sbin:/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"
    steam_runtime="${STEAM_RUNTIME-}"

    # Undo any weird environment before we start running external
    # executables. We put it back before running the actual app/game.

    if [ -n "${LD_LIBRARY_PATH-}" ]; then
        set -- "--steam-runtime-env=LD_LIBRARY_PATH=$LD_LIBRARY_PATH" "$@"
    fi

    if [ -n "${LD_AUDIT-}" ]; then
        set -- "--steam-runtime-env=LD_AUDIT=$LD_AUDIT" "$@"
    fi

    if [ -n "${LD_PRELOAD-}" ]; then
        set -- "--steam-runtime-env=LD_PRELOAD=$LD_PRELOAD" "$@"
    fi

    if [ -n "${PATH-}" ]; then
        set -- "--steam-runtime-env=PATH=$PATH" "$@"
    fi

    if [ -n "${STEAM_RUNTIME-}" ]; then
        set -- "--steam-runtime-env=STEAM_RUNTIME=$STEAM_RUNTIME" "$@"
    fi

    unset LD_AUDIT
    unset LD_LIBRARY_PATH
    unset LD_PRELOAD
    export PATH="$default_path"
    unset STEAM_RUNTIME

    if [ -n "${SYSTEM_LD_LIBRARY_PATH+set}" ]; then
        set -- "--steam-runtime-env=SYSTEM_LD_LIBRARY_PATH=$SYSTEM_LD_LIBRARY_PATH" "$@"
        export LD_LIBRARY_PATH="$SYSTEM_LD_LIBRARY_PATH"
    fi

    if [ -n "${SYSTEM_LD_PRELOAD+set}" ]; then
        set -- "--steam-runtime-env=SYSTEM_LD_PRELOAD=$SYSTEM_LD_PRELOAD" "$@"
        export LD_PRELOAD="$SYSTEM_LD_PRELOAD"
    fi

    if [ -n "${STEAM_RUNTIME_LIBRARY_PATH+set}" ]; then
        set -- "--steam-runtime-env=STEAM_RUNTIME_LIBRARY_PATH=$STEAM_RUNTIME_LIBRARY_PATH" "$@"
    fi

    if [ -n "${SYSTEM_PATH+set}" ]; then
        set -- "--steam-runtime-env=SYSTEM_PATH=$SYSTEM_PATH" "$@"
        export PATH="$SYSTEM_PATH"
    fi

    if [ -n "${PRESSURE_VESSEL_APP_LD_LIBRARY_PATH+set}" ]; then
        set -- "--steam-runtime-env=PRESSURE_VESSEL_APP_LD_LIBRARY_PATH=$PRESSURE_VESSEL_APP_LD_LIBRARY_PATH" "$@"
    fi

    if [ -x "$here/../libexec/steam-runtime-tools-0/launch-options.py" ]; then
        script="$here/../libexec/steam-runtime-tools-0/launch-options.py"
    elif [ -x "$here/${me%.sh}.py" ]; then
        script="$here/${me%.sh}.py"
    else
        # This will fail, and we'll show an error message
        script="$here/../libexec/steam-runtime-tools-0/launch-options.py"
    fi

    if ! result="$("$script" --check-gui-dependencies 2>&1)"; then
        result="$(printf '%s' "$result" | sed -e 's/&/\&amp;/' -e 's/</\&lt;/' -e 's/>/\&gt;/')"
        run="env"

        case "$steam_runtime" in
            (/*)
                # Re-enter the Steam Runtime, because STEAM_ZENITY might
                # not work otherwise
                run="$steam_runtime/run.sh"
                ;;
        esac

        if [ -e "$script" ]; then
            text="The pressure-vessel developer/debugging options menu requires Python 3, PyGI, GTK 3, and GTK 3 GObject-Introspection data.

    <small>$result</small>"
        else
            text="$result"
        fi

        "$run" "${STEAM_ZENITY:-zenity}" --error --width 500 --text "$text" || :
        exit 125
    fi

    exec "$script" "$@" || exit 125
}

main "$@"

# vim:set sw=4 sts=4 et:
