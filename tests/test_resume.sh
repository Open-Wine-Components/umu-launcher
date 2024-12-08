#!/usr/bin/env sh

tmp=$(mktemp)
# Request the BUILD_ID.txt value. We append this to the working file to ID it
id=$(curl -L "https://repo.steampowered.com/steamrt3/images/latest-container-runtime-public-beta/BUILD_ID.txt" | tr -d "\n")
# Request the first 100MB of the runtime archive
curl -LJO --range 0-104857599 "https://repo.steampowered.com/steamrt3/images/latest-container-runtime-public-beta/SteamLinuxRuntime_sniper.tar.xz"
mkdir -p "$HOME"/.cache/umu
# Move to our cache so it can be picked up then resumed.
# Note: Must include the *.parts extension
mv SteamLinuxRuntime_sniper.tar.xz "$HOME"/.cache/umu/SteamLinuxRuntime_sniper.tar.xz."$id".parts
UMU_LOG=debug GAMEID=umu-0 "$HOME/.local/bin/umu-run" wineboot -u 2> "$tmp"
grep "resuming" "$tmp" && grep "exited with wait status" "$tmp"
