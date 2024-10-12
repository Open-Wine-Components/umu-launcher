# Install dependencies:
```
Fedora:
sudo dnf install flatpak-builder

Ubuntu:
sudo apt install flatpak-builder
```

# Build + install (for testing):
```
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak-builder --force-clean --user --install-deps-from=flathub --repo=umu-repo --install umu-launcher org.openwinecomponents.umu.umu-launcher.yml
```

# Remove
```
flatpak --user remove umu-launcher
```

# Usage examples:

# winecfg:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.umu-launcher winecfg
```

# running a game using the default latest UMU-Proton:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.umu-launcher /path/to/some/game.exe
```

# running a game using the latest GE-Proton:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen --env=PROTONPATH=GE-Proton org.openwinecomponents.umu.umu-launcher /path/to/some/game.exe
```

# running a game using a specific proton version:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen --env=PROTONPATH=GE-Proton9-1 org.openwinecomponents.umu.umu-launcher /path/to/some/game.exe
```
