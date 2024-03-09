ulwgl(1)

# NAME

ulwgl-run - Unified Launcher for Windows Games on Linux

# SYNOPSIS

*ulwgl-run* [_OPTIONS_...] [_FILE_ [_ARG_...] | _FILE_]

# OPTIONS

*-h, --help*
	Show this help message.

*--config* <config>
	Path to TOML configuration file (Requires Python 3.11+).

	See *ulwgl*(5) for more info and examples.

# DESCRIPTION

The Unified Launcher for Windows Games on Linux (ULWGL) was created to make
Valve's Proton and the Protonfixes project accessible outside the Steam client,
providing a standardized way for other clients (e.g., Lutris, Heroic Games
Launcher, Bottles, or Rare) to run games via Proton and configure WINE
prefixes.

As a result, clients:
- No longer require Steam or Steam binaries to be installed
- Can contribute and benefit from Protonfixes
- Can run games through Proton as it were a native Steam game
- Can reference a unified online database of game fixes (Protonfixes)

You can run ULWGL directly from the tty, or through your launcher of 
choice if supported.

# EXAMPLES

*Example 1. Run a game*

```
$ WINEPREFIX= GAMEID=0 PROTONPATH= ulwgl-run ~/foo.exe
```

*Example 2. Run a game and apply a Protonfix*

```
# Applies a GOG Protonfix to the current WINE prefix
# See https://github.com/Open-Wine-Components/ULWGL-protonfixes
$ WINEPREFIX= GAMEID=ulwgl-1228964594 PROTONPATH= STORE=gog ulwgl-run ~/foo.exe
```

*Example 3. Run a game via a configuration file*

```
# config.toml
[ulwgl]
prefix = "~/.wine"
proton = "~/GE-Proton30"
game_id = "0"
exe = "~/foo.exe"
launch_args = "-opengl -SkipBuildPatchPrereq"
store = "gog"
$ ulwgl-run --config config.toml
```

*Example 4. Create a ULWGL WINE prefix*

```
$ WINEPREFIX=~/foo GAMEID=0 PROTONPATH= ulwgl-run ""
```

*Example 5. Run a game and automatically set Proton*

```
# First checks for a recent Proton at ~/.local/share/Steam/compatibilitytools.d
# When Proton cannot be found, the latest ULWGL-Proton will be downloaded
# The cache ~/.cache/ULWGL will be checked if the download fails or interrupted
$ WINEPREFIX= GAMEID=0 ulwgl-run foo.exe
```

*Example 6. Run a game, automatically set Proton, and create a WINE prefix*

```
# This will create the prefix as ~/Games/ULWGL/<ulwgl-$GAMEID>
$ GAMEID=0 ulwgl-run foo.exe
```

*Example 7. Run a game and explicitly set a valid Proton verb*

```
$ WINEPREFIX= GAMEID=0 PROTONPATH= PROTON_VERB=waitforexitandrun ulwgl-run ~/foo.exe
```

*Example 8. Run a game and enable debug logs*

```
# Shows environment variables and command at this level
# Valid values for ULWGL_LOG include: 1, warn, debug
$ ULWGL_LOG=1 WINEPREFIX= GAMEID=0 PROTONPATH= ulwgl-run ~/foo.exe
```

# AUTHORS

Maintained by Open Wine Components members, and assisted by other open source
contributors. For more information about ULWGL development, see
https://github.com/Open-Wine-Components/ULWGL-launcher.
