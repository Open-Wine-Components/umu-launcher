umu(1)

# NAME

umu-run - Unified Launcher for Windows Games on Linux

# SYNOPSIS

*umu-run* [_FILE_]

*umu-run* [_FILE_ [_ARG_...]]

*umu-run* [_winetricks_ [_ARG_...]]

*umu-run* *--config* [_FILE_]

*umu-run* *--help*

# POSITIONAL ARGUMENTS

*winetricks*
	Run *winetricks*[1] verbs (Requires GE-Proton or UMU-Proton).

	See *winetricks*(1) for more info or below for an example.

# OPTIONS

*-h, --help*
	Show this help message.

*--config* <config>
	Path to TOML configuration file (Requires Python 3.11+).

	See *umu*(5) for more info and examples.

# DESCRIPTION

The Unified Launcher for Windows Games on Linux (umu) was created to make
Valve's *Proton*[2] and the *protonfixes*[3] project accessible outside the
Steam client, providing a standardized way for other clients (e.g., Lutris,
Heroic Games Launcher, Bottles, or Rare) to run games via Proton and configure
WINE prefixes.

As a result, clients:
- No longer require Steam or Steam binaries to be installed
- Can contribute and automatically benefit from protonfixes
- Can run games through Proton as it were a native Steam game
- Can reference a unified online database of game fixes (protonfixes)

You can run umu directly from a terminal emulator, or through your launcher of 
choice if supported.

# EXAMPLES

*Example 1. Run a game*

```
$ WINEPREFIX=~/.wine GAMEID=0 PROTONPATH=~/GE-Proton9-4 umu-run foo.exe
```

*Example 2. Run a game and apply a specific protonfix*

```
# Applies the Star Citizen fix to the current WINE prefix
$ WINEPREFIX=~/.wine GAMEID=umu-starcitizen PROTONPATH=~/GE-Proton9-4 umu-run foo.exe
```

*Example 3. Run a game via a configuration file*

```
# config.toml
[umu]
prefix = "~/.wine"
proton = "~/GE-Proton30"
game_id = "0"
exe = "~/foo.exe"
launch_args = ["-opengl", "-SkipBuildPatchPrereq"]
store = "gog"
$ umu-run --config config.toml
```

*Example 4. Create a umu WINE prefix*

```
$ WINEPREFIX=~/foo GAMEID=0 PROTONPATH=~/GE-Proton9-4 umu-run ""
```

*Example 5. Run a game and automatically set Proton*

```
# Uses the latest UMU-Proton and automatically removes old UMU-Proton builds
$ WINEPREFIX=~/.wine GAMEID=0 umu-run foo.exe
```

*Example 6. Run a game, automatically set Proton, and create a WINE prefix*

```
# Creates the prefix as $HOME/Games/umu/$GAMEID and uses the latest UMU-Proton
$ GAMEID=0 umu-run foo.exe
```

*Example 7. Run a game and explicitly set a valid Proton verb*

```
$ WINEPREFIX=~/.wine GAMEID=0 PROTONPATH=~/GE-Proton9-4 PROTON_VERB=waitforexitandrun umu-run foo.exe
```

*Example 8. Run a game and enable debug logs*

```
$ UMU_LOG=debug WINEPREFIX=~/.wine GAMEID=0 PROTONPATH=~/GE-Proton9-4 umu-run foo.exe
```

*Example 9. Run a game and set a Proton by its version name*

```
# Checks for GE-Proton9-1 at $HOME/.local/share/Steam/compatibilitytools.d
$ WINEPREFIX=~/.wine GAMEID=0 PROTONPATH=GE-Proton9-1 umu-run foo.exe
```

*Example 10. Run a game and automatically use the latest GE-Proton*

```
$ WINEPREFIX=~/.wine GAMEID=0 PROTONPATH=GE-Proton umu-run foo.exe
```

*Example 11. Run winetricks verbs*

```
$ GAMEID=0 PROTONPATH=GE-Proton umu-run winetricks quartz wmp11 qasf
```

*Example 12. Run a game, but do not apply protonfixes*

```
$ GAMEID=umu-1228964594 PROTONPATH=GE-Proton PROTONFIXES_DISABLE=1 umu-run foo.exe
```

# ENVIRONMENT VARIABLES

_GAMEID_
	Required. Can be an arbitrary value or a valid id in the *umu-database*[4].

_PROTONPATH_
	Optional. Path to a Proton directory, version name (e.g., GE-Proton9-5) or codename (e.g., GE-Proton).
	
	Otherwise, defaults to using UMU-Proton.

_WINEPREFIX_
	Optional. Path to a WINE prefix directory. Otherwise defaults to _$HOME/Games/umu/$GAMEID_.

_UMU_LOG_
	Optional. Enables debug logs for the launcher.
	
	Set _1_ to log environment variables, _warning_ for warning messages, or _debug_ to enable all logs.

_STORE_
	Optional. Can be an arbitrary value or a valid store id in the umu-database.

_PROTON_VERB_
	Optional. Must be a valid Proton verb. Otherwise, defaults to _waitforexitandrun_.

_UMU_ZENITY_
	Optional. Creates a *zenity*[5] popup window when downloading large files.

_UMU_RUNTIME_UPDATE_
	Optional. Disables automatic updates to the *Steam Linux Runtime*[6].

	Set _0_ to disable updates.

# SEE ALSO

_umu_(5), _winetricks_(1), _zenity_(1)

# NOTES

. https://github.com/Winetricks/winetricks
. https://github.com/ValveSoftware/Proton
. https://github.com/Open-Wine-Components/umu-protonfixes
. https://github.com/Open-Wine-Components/umu-database
. https://gitlab.gnome.org/GNOME/zenity
. https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/container-runtime.md

# AUTHORS

Maintained by Open Wine Components members, and assisted by other open source
contributors. For more information about umu development, see
https://github.com/Open-Wine-Components/umu-launcher.
