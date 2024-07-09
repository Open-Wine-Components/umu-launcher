1. Install build dependencies:

snap install snapcraft --classic

2. Create snap structure:

mkdir snap
cp snapcraft.yaml snap/

3. Build:
snapcraft

4. Install:

snap install --dangerous --devmode umu-launcher*.snap

5. Test:

WINEPREFIX=~/umu-test STORE=none GAMEID=0 umu-launcher.umu-run winecfg
