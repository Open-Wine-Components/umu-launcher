#!/usr/bin/env sh

tmp=$(mktemp)
name=$(curl -L "https://api.github.com/repos/Open-Wine-Components/umu-proton/releases/latest" | jq .assets[1].name | tr -d '"')
url=$(curl -L "https://api.github.com/repos/Open-Wine-Components/umu-proton/releases/latest" | jq .assets[1].browser_download_url | tr -d '"')
# Request the first 100MB of the latest UMU-Proton release
curl -LJO --range 0-104857599 "$url"
# Move the incomplete file to our cache to be picked up
# Note: Must include the *.parts extension
mkdir -p "$HOME"/.cache/umu
mv "$name" "$HOME"/.cache/umu/"$name".parts
UMU_LOG=debug GAMEID=umu-0 "$HOME/.local/bin/umu-run" wineboot -u 2> "$tmp"
grep "resuming" "$tmp" && grep "exited with wait status" "$tmp"
