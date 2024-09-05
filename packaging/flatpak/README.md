# CLI

## Install dependencies:
```
Fedora:
sudo dnf install flatpak-builder

Ubuntu:
sudo apt install flatpak-builder
```

## Build + install (for testing):
```
flatpak-builder --force-clean --user --install-deps-from=flathub --repo=umu-repo --install umu-launcher org.openwinecomponents.umu.umu-launcher.yml
```

## Remove
```
flatpak --user remove umu-launcher
```

## Usage examples:

## winecfg:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.umu-launcher winecfg
```

## running a game using the default latest UMU-Proton:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.umu-launcher /path/to/some/game.exe
```

## running a game using the latest GE-Proton:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.umu-launcher --env=PROTONPATH=GE-Proton /path/to/some/game.exe
```

## running a game using a specific proton version:
```
flatpak run --env=GAMEID=umu-starcitizen --env=WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen org.openwinecomponents.umu.umu-launcher --env=PROTONPATH=GE-Proton9-1 /path/to/some/game.exe
```

# As part of another flatpak app

In order to have umu-run available in your flatpak app.
Include the [umu-launcher.json](umu-launcher.json) in manifest 

```yaml
modules:
  - 'umu-launcher.json'
```

## Add a filesystem permission

This is a common location where the runtime will be extracted.
Using the host path is crucial for being able to share the runtime with other applications using umu. This is done for storage saving purposes.

```yaml
finish-args:
  - --filesystem=xdg-data/umu
```

## Additional finish args

The following args may be required for pressure-vessel to work properly

```yaml
finish-args:
  - --allow=per-app-dev-shm
  # Wine uses UDisks2 to enumerate disk drives
  - --system-talk-name=org.freedesktop.UDisks2
  # Required for bwrap to work
  - --talk-name=org.freedesktop.portal.Background
  # Pressure Vessel
  # See https://github.com/flathub/com.valvesoftware.Steam/commit/0538256facdb0837c33232bc65a9195a8a5bc750
  - --env=XDG_DATA_DIRS=/app/share:/usr/lib/extensions/vulkan/share:/usr/share:/usr/share/runtime/share:/run/host/user-share:/run/host/share:/usr/lib/pressure-vessel/overrides/share
```

