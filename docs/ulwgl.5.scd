ulwgl(5)

# NAME

ulwgl-run - configuration file

# DESCRIPTION

ulwgl-run can optionally read a configuration file instead of reading
environment variables set from the command line. The configuration file for
ulwgl-run must be written in valid Tom's Obvious Minimal Language (TOML).

In the configuration file, the table *ulwgl* is required as well as the keys
*prefix*, *proton* and *exe* which all must be basic strings. e.g.:

```
[ulwgl]
prefix = "~/WINE/epic-games-store"
exe = "~/EpicGamesLauncher.exe"
proton = "~/.local/share/Steam/compatibilitytools.d/GE-Proton30"
```

Afterwards, run the command:
```
$ ulwgl-run --config config.toml
```

# [ulwgl] SECTION

*exe*
	Path to the game executable to run. Value must be a basic *string*.

*proton*
	Path to a Proton directory. Value must be a basic *string*.

*prefix*
	Path to a WINE prefix directory. Value must be a basic *string*.

*game_id*
	The ULWGL id to assign to the game. Depending on the value assigned, a Proton
	fix will be applied to the prefix if available. Please refer to the ULWGL
	database for an extended list of game ids.

*store*
	The distribution platform of the executable. Value must be a basic *string*.
	Expects the values: egs, gog, battlenet, amazon, humble, itchio, and ubisoft.

*launch_args*
	Launch arguments for the executable. Value must be a basic *string*.
	Assumes each argument is space-separated.

# AUTHORS

Maintained by Open Wine Components members, and assisted by other open source
contributors. For more information about ULWGL development, see
https://github.com/Open-Wine-Components/ULWGL-launcher.
