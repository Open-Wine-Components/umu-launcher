# Install dependencies:
```
flatpak --user install org.freedesktop.Sdk/x86_64/23.08
flatpak --user install org.freedesktop.Sdk.Compat.i386/x86_64/23.08
flatpak --user install org.freedesktop.Sdk.Extension.toolchain-i386/x86_64/23.08
```

# Build:
```
flatpak-builder umu-launcher org.openwinecomponents.umu.launcher.yml
flatpak-builder --repo=umu-repo --force-clean umu-launcher org.openwinecomponents.umu.launcher.yml
```

# Install:
```
flatpak --user remote-add --no-gpg-verify umu-repo umu-repo
flatpak --user install umu-repo org.openwinecomponents.umu.launcher
```

# Build + install without repo (for testing):
```
flatpak-builder umu-launcher org.openwinecomponents.umu.launcher.yml --install --user --force-clean
```

# Usage examples:

# winecfg:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.launcher winecfg
```

# running a game using the default latest UMU-Proton:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.launcher winecfg /path/to/some/game.exe
```

# running a game using the latest GE-Proton:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.launcher --env=PROTONPATH=GE-Proton /path/to/some/game.exe
```

# running a game using a specific proton version:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.launcher --env=PROTONPATH=GE-Proton9-1 /path/to/some/game.exe
```
