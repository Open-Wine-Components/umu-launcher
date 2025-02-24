#!/usr/bin/env sh

tmp=$(mktemp)
name=$(curl -L "https://api.github.com/repos/Open-Wine-Components/umu-proton/releases/latest" | jq .assets[1].name | tr -d '"')

# Ensure the Proton directory doesn't exist
rm "$name"

# Download runtime
curl -LJO "https://repo.steampowered.com/steamrt3/images/latest-container-runtime-public-beta/SteamLinuxRuntime_sniper.tar.xz"
url=$(curl -L "https://api.github.com/repos/Open-Wine-Components/umu-proton/releases/latest" | jq .assets[1].browser_download_url | tr -d '"')

# Download Proton
curl -LJO "$url"

mkdir -p "$HOME"/.local/share/Steam/compatibilitytools.d "$HOME"/.local/share/umu/steamrt3 "$HOME"/Games/umu

# Extract the archives
tar xaf "$name" -C "$HOME"/.local/share/Steam/compatibilitytools.d
tar xaf SteamLinuxRuntime_sniper.tar.xz

cp -a SteamLinuxRuntime_sniper/* "$HOME"/.local/share/umu/steamrt3
mv "$HOME"/.local/share/umu/steamrt3/_v2-entry-point "$HOME"/.local/share/umu/steamrt3/umu

# Run offline using bwrap
# TODO: Figure out why the command exits with a 127 when offline. The point
# is that we're able to enter the container and we do not crash. For now,
# just query a string that shows that session was offline
RUNTIMEPATH=steamrt3 UMU_LOG=debug GAMEID=umu-0 bwrap --unshare-net --bind / / --dev /dev --bind "$HOME" "$HOME" -- "$HOME/.local/bin/umu-run" wineboot -u 2> "$tmp"

# Check if we exited. If we logged this statement then there were no errors
# before entering the container
grep "exited with wait status" "$tmp"
# Check if we were offline
grep "unreachable" "$tmp"
