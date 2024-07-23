# Install dependencies:
```
sudo dnf install -y mock fedpkg
sudo usermod -aG mock username
su username
```

# Build:
```
fedpkg --release f40 srpm
mock -r /etc/mock/fedora-40-x86_64.cfg --rebuild --enable-network *.src.rpm
mv /var/lib/mock/fedora-40-x86_64/result .
```

# Install:
```
cd result
sudo dnf install -y  umu-launcher*.rpm
```

# Remove
```
sudo dnf remove -y umu-launcher
```

# Usage examples:

# winecfg:
```
GAMEID=umu-starcitizen WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen umu-run winecfg
```

# running a game using the default latest UMU-Proton:
```
GAMEID=umu-starcitizen WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen umu-run  /path/to/some/game.exe
```

# running a game using the latest GE-Proton:
```
GAMEID=umu-starcitizen WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen PROTONPATH=GE-Proton umu-run /path/to/some/game.exe
```

# running a game using a specific proton version:
```
GAMEID=umu-starcitizen WINEPREFIX=/home/tcrider/Games/umu/umu-starcitizen PROTONPATH=GE-Proton9-1 umu-run /path/to/some/game.exe
```
