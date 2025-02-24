#!/usr/bin/env sh

tmp=$(mktemp)
mkdir -p "$HOME/.local/share/Steam/compatibilitytools.d"
curl -LJO "https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton7-55/GE-Proton7-55.tar.gz"
tar xaf GE-Proton7-55.tar.gz
mv GE-Proton7-55 "$HOME/.local/share/Steam/compatibilitytools.d"

UMU_LOG=debug PROTONPATH=GE-Proton7-55 "$HOME/.local/bin/umu-run" wineboot -u
