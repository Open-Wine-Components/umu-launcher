#!/usr/bin/env sh

mkdir -p "$HOME/.local/share/umu"

curl -LJO "https://repo.steampowered.com/steamrt3/images/0.20240916.101795/SteamLinuxRuntime_sniper.tar.xz"
tar xaf SteamLinuxRuntime_sniper.tar.xz
mv SteamLinuxRuntime_sniper/* "$HOME/.local/share/umu"
mv "$HOME/.local/share/umu/_v2-entry-point" "$HOME/.local/share/umu/umu"

# Perform a preflight step, where we ensure everything is in order and create '$HOME/.local/share/umu/var'
# Afterwards, run a 2nd time to perform the runtime update and ensure '$HOME/.local/share/umu/var' is removed
UMU_LOG=debug GAMEID=umu-0 UMU_RUNTIME_UPDATE=0 "$HOME/.local/bin/umu-run" wineboot -u && UMU_LOG=debug GAMEID=umu-0 "$HOME/.local/bin/umu-run" wineboot -u
