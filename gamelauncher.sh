#!/bin/bash

set -x

if [[ -z $1 ]] || [[ -z $WINEPREFIX ]] || [[ -z $GAMEID ]] || [[ -z $PROTONPATH ]]; then
 echo 'Usage: WINEPREFIX=<wine-prefix-path> GAMEID=<ulwgl-id> PROTONPATH=<proton-version-path> ./gamelauncher.sh <executable-path> <arguments>'
 echo 'Ex:'
 echo 'WINEPREFIX=$HOME/Games/epic-games-store GAMEID=egs PROTONPATH="$HOME/.steam/steam/compatibilitytools.d/GE-Proton8-28" ./gamelauncher.sh "$HOME/Games/epic-games-store/drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe" "-opengl -SkipBuildPatchPrereq"'
 exit 1
fi
if [[ $WINEPREFIX ]]; then
   if [[ ! -d "$WINEPREFIX" ]]; then
     mkdir -p "$WINEPREFIX"
   fi
   ln -s "$WINEPREFIX" "$WINEPREFIX"/pfx
   touch "$WINEPREFIX"/tracked_files
fi
export PROTONPATH="$PROTONPATH"
export ULWGL_ID="$GAMEID"
export STEAM_COMPAT_APP_ID="$GAMEID"
numcheck='^[0-9]+$'
if [[ $(cat $ULWGL_ID | cut -d "-" -f 2) =~$numcheck ]]; then
  export STEAM_COMPAT_APP_ID=$(cat $ULWGL_ID | cut -d "-" -f 2)
fi
export SteamAppId="$STEAM_COMPAT_APP_ID"
export STEAM_COMPAT_TOOL_PATHS=''
export STEAM_COMPAT_LIBRARY_PATHS=''
export STEAM_COMPAT_MOUNTS=''
export STEAM_COMPAT_INSTALL_PATH="$PROTONPATH"
export STEAM_COMPAT_CLIENT_INSTALL_PATH=''
export STEAM_COMPAT_DATA_PATH="$WINEPREFIX"
export STEAM_COMPAT_SHADER_PATH="$STEAM_COMPAT_DATA_PATH"/shadercache

export PROTON_CRASH_REPORT_DIR='/tmp/ULWGL_crashreports'
export FONTCONFIG_PATH=''

export EXE="$1"
shift 1
export LAUNCHARGS="$@"
me="$(readlink -f "$0")"
here="${me%/*}"
$here/ULWGL --verb=waitforexitandrun -- "$PROTONPATH"/proton waitforexitandrun "$EXE" "$1" "$2" "$3"
