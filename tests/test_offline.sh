#!/usr/bin/env sh

name=$(curl -L "https://api.github.com/repos/Open-Wine-Components/umu-proton/releases/latest" | jq .assets[1].name | tr -d '"')

# Ensure the Proton directory doesn't exist
rm "$name"

# Download runtime
curl -LJO "https://repo.steampowered.com/steamrt3/images/latest-container-runtime-public-beta/SteamLinuxRuntime_sniper.tar.xz"
url=$(curl -L "https://api.github.com/repos/Open-Wine-Components/umu-proton/releases/latest" | jq .assets[1].browser_download_url | tr -d '"')

# Download Proton
curl -LJO "$url"

mkdir -p "$HOME"/.local/share/compatibilitytools.d "$HOME"/.local/share/umu

# Extract the archives
tar xaf "$name" -C "$HOME"/.local/share/compatibilitytools.d
tar xaf SteamLinuxRuntime_sniper.tar.xz

cp -a SteamLinuxRuntime_sniper/* "$HOME"/.local/share/umu
mv "$HOME"/.local/share/umu/_v2-entry-point "$HOME"/.local/share/umu/umu

# Run offline using bwrap
UMU_LOG=debug GAMEID=umu-0 bwrap --unshare-net --bind / / --dev /dev -- "$HOME/.local/bin/umu-run" ""
