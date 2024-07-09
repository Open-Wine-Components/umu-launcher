## NOTICE ##

Due to the mounting and security requirements of pressure-vessel it is unfortunately unlikely that this will ever be accepted as an official snap within the snap store.

With that being said, we have put the snap together for convenience for those that wish to use it in snap-based environments.

Please be aware that this runs in devmode with without any standard snap confinements.

1. Install build dependencies:  
```
snap install snapcraft --classic
```
2. Create snap structure:  
```
mkdir snap
cp snapcraft.yaml snap/
```
3. Build:  
```  
snapcraft
```
4. Install:    
```
sudo snap install --dangerous --devmode umu-launcher*.snap
```
5. Test:  
```
sudo snap connect umu-launcher:gaming-mesa gaming-graphics-core22
WINEPREFIX=~/umu-test STORE=none GAMEID=0 umu-launcher.umu-run winecfg
```
