# Copy debian packaging folder to the repository root:
```
cp -rvf ./packaging/deb/debian ./
```


# Install build dependencies:
```
sudo apt install -y dh-make dpkg-dev
```

# Setup dh_make quilt files
```
LOGNAME=root dh_make --createorig -y -l -p umu-launcher_{PUT UMU VERSION HERE}
```

# Install apt build dependencies:
```
sudo apt build-dep -y ./ 
```

# Build:
```
dpkg-buildpackage --no-sign
```

# Install:
```
sudo apt install -y ../umu-launcher*.deb ../python3-umu-launcher*.deb
```

# Remove
```
sudo apt remove -y umu-launcher python3-umu-launcher
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
