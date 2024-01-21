#!/bin/bash

set -x

if [[ -z $1 ]] || [[ -z $2 ]] || [[ -z $WINEPREFIX ]] || [[ -z $GAMEID ]]; then
 echo "Usage: WINEPREFIX=/path-to-prefix GAMEID=makeoneup ./gamelauncher.sh <proton-path> <executable-path> <arguements>"
 echo 'Ex: WINEPREFIX=$HOME/Games/epic-games-store GAMEID=egs ./gamelauncher.sh "$HOME/.steam/steam/compatibilitytools.d/GE-Proton8-28" "$HOME/Games/epic-games-store/drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe" "-opengl -SkipBuildPatchPrereq"'
 exit 1
fi
if [[ $WINEPREFIX ]]; then
   if [[ ! -d "$WINEPREFIX" ]]; then
     mkdir -p "$WINEPREFIX"
   fi
   ln -s "$WINEPREFIX" "$WINEPREFIX"/pfx
   touch "$WINEPREFIX"/tracked_files
fi
export PROTONPATH="$1"
export STEAM_COMPAT_APP_ID="$GAMEID"
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

export EXE="$2"
export LAUNCHARGS="$3"

./ULWGL --verb=waitforexitandrun -- "$PROTONPATH"/proton waitforexitandrun "$EXE" "$LAUNCHARGS"
