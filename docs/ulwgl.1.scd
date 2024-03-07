ulwgl(1)

# NAME

ulwgl-run - Unified Launcher for Windows Games on Linux

# SYNOPSIS

*ulwgl-run* [_OPTIONS_...] [_FILE_ [_ARG_...] | _FILE_]

# OPTIONS

*-h, --help*
	Show this help message

*--config* <config>
	Path to TOML configuration file (Requires Python 3.11+)

	See *ulwgl*(5) for more info and examples

# EXAMPLES

```
# Play a game
$ WINEPREFIX= GAMEID=0 PROTONPATH= ulwgl-run ~/foo.exe
```

```
# Play a game and apply a GOG Protonfix
# Can be a Steam or non-Steam game
$ WINEPREFIX= GAMEID=ulwgl-1228964594 PROTONPATH= STORE=gog ulwgl-run ~/foo.exe
```

```
# Play a non-Steam game by reading a configuration file
[ulwgl]
prefix = "~/.wine"
proton = "~/GE-Proton30"
game_id = "0"
exe = "~/foo.exe"
launch_args = "-opengl -SkipBuildPatchPrereq"
store = "gog"
$ ulwgl-run --config config.toml
```

```
# Create a ULWGL WINE prefix
$ WINEPREFIX=~/foo GAMEID=0 PROTONPATH= ulwgl-run ""
```

```
# Play a game and download the latest ULWGL-Proton
$ WINEPREFIX= GAMEID=0 ulwgl-run foo.exe
```

```
# Play a game and automatically set Proton
# Will first search ~/.local/share/Steam/compatibilitytools.d for latest
# When a Proton cannot be found, ULWGL-Proton will be downloaded
$ WINEPREFIX= GAMEID=0 ulwgl-run foo.exe
```

```
# Play a game, automatically set Proton and create a prefix
# This will create the prefix as ~/Games/ULWGL/<ulwgl-$GAMEID>
$ GAMEID=0 ulwgl-run foo.exe
```

```
# Play a game and explicitly set a valid Proton verb
$ WINEPREFIX= GAMEID=0 PROTONPATH= PROTON_VERB=waitforexitandrun ulwgl-run ~/foo.exe
```

```
# Play a game and enable debug logs
# Valid values include: 1, warn, debug
$ ULWGL_LOG=1 WINEPREFIX= GAMEID=0 PROTONPATH= ulwgl-run ~/foo.exe
```

# AUTHORS

Maintained by Open Wine Components members, and assisted by other open source
contributors. For more information about ULWGL development, see
https://github.com/Open-Wine-Components/ULWGL-launcher.
