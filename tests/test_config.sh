#!/usr/bin/env sh

python --version

tmp=$(mktemp)
mkdir -p "$HOME/.local/share/Steam/compatibilitytools.d"
mkdir -p "$HOME/Games/umu/umu-0"
curl -LJO "https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton9-15/GE-Proton9-15.tar.gz"
tar xaf GE-Proton9-15.tar.gz
mv GE-Proton9-15 "$HOME/.local/share/Steam/compatibilitytools.d"

echo "[umu]
proton = '~/.local/share/Steam/compatibilitytools.d/GE-Proton9-15'
game_id = 'umu-0'
prefix = '~/Games/umu/umu-0'
exe = '~/.wine/drive_c/windows/syswow64/wineboot.exe'
launch_args = ['-u']
" >> "$tmp"


UMU_LOG=debug GAMEID=umu-0 "$PWD/.venv/bin/python" "$HOME/.local/bin/umu-run" --config "$tmp"
