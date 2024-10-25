#!/usr/bin/env sh

python --version

tmp=$(mktemp)
mkdir -p "$HOME/.local/share/Steam/compatibilitytools.d"
mkdir -p "$HOME/Games/umu/umu-0"
curl -LJO "https://github.com/Open-Wine-Components/umu-proton/releases/download/UMU-Proton-9.0-3.2/UMU-Proton-9.0-3.2.tar.gz"
tar xaf UMU-Proton-9.0-3.2.tar.gz
mv UMU-Proton-9.0-3.2 "$HOME/.local/share/Steam/compatibilitytools.d"

echo "[umu]
proton = '~/.local/share/Steam/compatibilitytools.d/UMU-Proton-9.0-3.2'
game_id = 'umu-1141086411'
prefix = '~/Games/umu/umu-0'
exe = '~/Games/umu/umu-0/drive_c/windows/syswow64/wineboot.exe'
launch_args = ['-u']
" >> "$tmp"


# Run the 'game' and ensure the protonfixes module finds its fix in umu-database.csv
UMU_LOG=debug GAMEID=umu-1141086411 STORE=gog "$PWD/.venv/bin/python" "$HOME/.local/bin/umu-run" --config "$tmp" >> /tmp/umu-log.txt && grep -E "INFO: Non-steam game Silent Hill 4: The Room \(umu-1141086411\)" /tmp/umu-log.txt
