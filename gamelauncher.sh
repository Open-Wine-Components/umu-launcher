#!/bin/sh

# use for debug only.
# set -x

# shellcheck disable=SC2016
if [ -z "$1" ] || [ -z "$WINEPREFIX" ] || [ -z "$GAMEID" ]; then
 echo 'Usage: WINEPREFIX=<wine-prefix-path> GAMEID=<ulwgl-id> PROTONPATH=<proton-version-path> ./gamelauncher.sh <executable-path> <arguments>'
 echo 'Ex:'
 echo 'WINEPREFIX=$HOME/Games/epic-games-store GAMEID=egs PROTONPATH="$HOME/.steam/steam/compatibilitytools.d/GE-Proton8-28" ./gamelauncher.sh "$HOME/Games/epic-games-store/drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe" "-opengl -SkipBuildPatchPrereq"'
 exit 1
fi

ULWGL_PROTON_VER="ULWGL-Proton-8.0-5"

if [ "$WINEPREFIX" ]; then
   if [ ! -d "$WINEPREFIX" ]; then
     mkdir -p "$WINEPREFIX"
     export PROTON_DLL_COPY="*"
   fi
   if [ ! -d "$WINEPREFIX"/pfx ]; then
     ln -s "$WINEPREFIX" "$WINEPREFIX"/pfx >/dev/null 2>&1
   fi
   if [ ! -f "$WINEPREFIX"/tracked_files ]; then
     touch "$WINEPREFIX"/tracked_files
   fi
   if [ ! -f "$WINEPREFIX/dosdevices/" ]; then
     mkdir -p "$WINEPREFIX"/dosdevices
     ln -s "../drive_c" "$WINEPREFIX/dosdevices/c:" >/dev/null 2>&1
   fi
fi
if [ -n "$PROTONPATH" ]; then
  if [ ! -d "$PROTONPATH" ]; then
    echo "ERROR: $PROTONPATH is invalid, aborting!"
    exit 1
  fi
fi
if [ -z "$PROTONPATH" ]; then
  if [ ! -d "$PWD"/ULWGL-Proton-Stable ]; then
    wget https://github.com/Open-Wine-Components/ULWGL-Proton/releases/download/$ULWGL_PROTON_VER/$ULWGL_PROTON_VER.tar.gz
    wget https://github.com/Open-Wine-Components/ULWGL-Proton/releases/download/$ULWGL_PROTON_VER/$ULWGL_PROTON_VER.sha512sum
    if echo "$(cat $ULWGL_PROTON_VER.sha512sum) $ULWGL_PROTON_VER.tar.gz" | sha512sum -cs; then
      tar -zxvf $ULWGL_PROTON_VER.tar.gz --one-top-level="$PWD"/ULWGL-Proton-Stable
      rm $ULWGL_PROTON_VER.tar.gz
      rm $ULWGL_PROTON_VER.sha512sum
    else
      echo "ERROR: $ULWGL_PROTON_VER.tar.gz checksum does not match $ULWGL_PROTON_VER.sha512sum, aborting!"
      rm $ULWGL_PROTON_VER.tar.gz
      rm $ULWGL_PROTON_VER.sha512sum
      exit 1
    fi
  fi
  PROTONPATH="$PWD"/ULWGL-Proton-Stable/$ULWGL_PROTON_VER
else
  export PROTONPATH="$PROTONPATH"
fi
export ULWGL_ID="$GAMEID"
export STEAM_COMPAT_APP_ID="0"
if printf %d "${ULWGL_ID##*-}" >/dev/null 2>&1; then
  export STEAM_COMPAT_APP_ID="${ULWGL_ID##*-}"
fi
export SteamAppId="$STEAM_COMPAT_APP_ID"
export SteamGameId="$STEAM_COMPAT_APP_ID"

# TODO: Ideally this should be the main game install path, which is often, but not always the path of the game's executable.
if [ -z "$STEAM_COMPAT_INSTALL_PATH" ]; then
  exepath="$(readlink -f "$1")"
  gameinstallpath="${exepath%/*}"
  export STEAM_COMPAT_INSTALL_PATH="$gameinstallpath"
fi

compat_lib_path=$(findmnt -T "$STEAM_COMPAT_INSTALL_PATH" | tail -n 1 | awk '{ print $1 }')
if [ "$compat_lib_path" != "/" ]; then
    export STEAM_COMPAT_LIBRARY_PATHS="${STEAM_COMPAT_LIBRARY_PATHS:+"${STEAM_COMPAT_LIBRARY_PATHS}:"}$compat_lib_path"
fi

if [ -z "$STEAM_RUNTIME_LIBRARY_PATH" ]; then
  # The following info taken from steam ~/.local/share/ubuntu12_32/steam-runtime/run.sh
  host_library_paths=
  exit_status=0
  ldconfig_output=$(/sbin/ldconfig -XNv 2> /dev/null; exit $?) || exit_status=$?
  if [ $exit_status != 0 ]; then
      echo "Warning: An unexpected error occurred while executing \"/sbin/ldconfig -XNv\", the exit status was $exit_status"
  fi

  while read -r line; do
    # If line starts with a leading / and contains :, it's a new path prefix
    case "$line" in /*:*)
        library_path_prefix=$(echo "$line" | cut -d: -f1)

        host_library_paths=$host_library_paths$library_path_prefix:
    esac
  done <<EOLDCONFIG
$ldconfig_output
EOLDCONFIG

  host_library_paths="${LD_LIBRARY_PATH:+"${LD_LIBRARY_PATH}:"}$host_library_paths"
  steam_runtime_library_paths="${STEAM_COMPAT_INSTALL_PATH}:${host_library_paths}"
  export STEAM_RUNTIME_LIBRARY_PATH="$steam_runtime_library_paths"
fi

if [ -z "$PROTON_VERB" ]; then
  export PROTON_VERB="waitforexitandrun"
fi

export STEAM_COMPAT_CLIENT_INSTALL_PATH=''
export STEAM_COMPAT_DATA_PATH="$WINEPREFIX"
export STEAM_COMPAT_SHADER_PATH="$STEAM_COMPAT_DATA_PATH"/shadercache

export PROTON_CRASH_REPORT_DIR='/tmp/ULWGL_crashreports'
export FONTCONFIG_PATH=''

export EXE="$1"
if [ "$EXE" = "createprefix"  ]; then
	# Hack, leave empty.
	# forces proton to create a prefix without actually running anything.
	EXE=""
fi
shift 1

me="$(readlink -f "$0")"
here="${me%/*}"

export STEAM_COMPAT_TOOL_PATHS="$PROTONPATH:$here"
export STEAM_COMPAT_MOUNTS="$PROTONPATH:$here"

"$here"/ULWGL "--verb=$PROTON_VERB" -- "$PROTONPATH"/proton "$PROTON_VERB" "$EXE" "$@"

