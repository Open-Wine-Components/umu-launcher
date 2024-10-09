#!/usr/bin/env sh

python --version

tmp=$(mktemp)
mkdir -p "$HOME/.local/share/Steam/compatibilitytools.d"
mkdir -p "$HOME/Games/umu/umu-0"
curl -LJO "https://github.com/Open-Wine-Components/umu-proton/releases/download/UMU-Proton-9.0-3/UMU-Proton-9.0-3.tar.gz"
tar xaf UMU-Proton-9.0-3.tar.gz
mv UMU-Proton-9.0-3 "$HOME/.local/share/Steam/compatibilitytools.d"

echo "[umu]
proton = '~/.local/share/Steam/compatibilitytools.d/UMU-Proton-9.0-3'
game_id = 'umu-0'
prefix = '~/Games/umu/umu-0'
exe = '~/Games/umu/umu-0/drive_c/windows/syswow64/wineboot.exe'
launch_args = ['-u']
" >> "$tmp"


UMU_LOG=debug GAMEID=umu-0 "$PWD/.venv/bin/python" "$HOME/.local/bin/umu-run" --config "$tmp"
