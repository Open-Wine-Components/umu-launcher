#!/usr/bin/env sh

mkdir -p "$HOME/.local/share/umu/steamrt3"

curl -LJO "https://repo.steampowered.com/steamrt3/images/0.20240916.101795/SteamLinuxRuntime_sniper.tar.xz"
tar xaf SteamLinuxRuntime_sniper.tar.xz
mv SteamLinuxRuntime_sniper/* "$HOME/.local/share/umu/steamrt3"
mv "$HOME/.local/share/umu/steamrt3/_v2-entry-point" "$HOME/.local/share/umu/steamrt3/umu"
echo "$@" > "$HOME/.local/share/umu/steamrt3/umu-shim" && chmod 700 "$HOME/.local/share/umu/steamrt3/umu-shim"

# Perform a preflight step, where we ensure everything is in order and create '$HOME/.local/share/umu/var'
# Afterwards, run a 2nd time to perform the runtime update and ensure '$HOME/.local/share/umu/var' is removed
UMU_LOG=debug GAMEID=umu-0 UMU_RUNTIME_UPDATE=0 "$HOME/.local/bin/umu-run" wineboot -u && RUNTIMEPATH=steamrt3 UMU_LOG=debug GAMEID=umu-0 "$HOME/.local/bin/umu-run" wineboot -u
