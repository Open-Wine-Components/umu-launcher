# ULWGL
Unified Linux Wine Game Launcher


# WHAT IS THIS?

This is a unified launcher for windows games on linux. It is essentially a copy of the Steam Linux Runtime/Steam Runtime Tools (https://gitlab.steamos.cloud/steamrt/steam-runtime-tools) that Valve uses for proton, with some modifications made so that it can be used outside of Steam.

# WHAT DOES IT DO?

When steam launches a proton game, it launches it like this:

```
/home/tcrider/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=348550 -- /home/tcrider/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- /home/tcrider/.local/share/Steam/steamapps/common/SteamLinuxRuntime_sniper/_v2-entry-point --verb=waitforexitandrun -- /home/tcrider/.local/share/Steam/compatibilitytools.d/GE-Proton8-27/proton waitforexitandrun /home/tcrider/.local/share/Steam/steamapps/common/Guilty Gear XX Accent Core Plus R/GGXXACPR_Win.exe
```

We can ignore this `/home/tcrider/.local/share/Steam/ubuntu12_32/steam-launch-wrapper`, it's just a process runner with no real value other than forwarding environment variables (more on that later).

I managed to pull the envvars it uses by making steam run printenv for the games command line. We needed these envvars because proton expects them in order to function. With them we can essentially make proton run without needing steam at all.

Next this part `/home/tcrider/.local/share/Steam/steamapps/common/SteamLinuxRuntime_sniper/_v2-entry-point`

The first part `/home/tcrider/.local/share/Steam/steamapps/common/SteamLinuxRuntime_sniper/` is steam-runtime-tools compiled https://gitlab.steamos.cloud/steamrt/steam-runtime-tools and is used alongside the sniper runtime container used during proton builds.

The second part `_v2-entry-point` is just a bash script which loads proton into the container and runs the game.

So, ULWGL is basically a copy paste of SteamLinuxRuntime_sniper, which is a compiled version of steam-runtime-tools. We've renamed _v2-entry-point to ULWGL and added `ulwgl-run` to replace steam-launch-wrapper.

When you use `ulwgl-run` to run a game, it uses the specified WINEPREFIX, proton version, executable, and arguements passed to it to run the game in proton, inside steam's runtime container JUST like if you were running the game through Steam, except now you're no longer limited to Steam's game library or forced to add the game to Steam's library, in fact, you don't even have to have steam installed.

# HOW DO I USE IT?

Usage:

  `WINEPREFIX=<wine-prefix-path> GAMEID=<ulwgl-id> PROTONPATH=<proton-version-path> ./ulwgl-run <executable-path> <arguements>`

Ex:

  `WINEPREFIX=$HOME/Games/epic-games-store GAMEID=ulwgl-dauntless PROTONPATH="$HOME/.steam/steam/compatibilitytools.d/GE-Proton8-28" ./ulwgl-run "$HOME/Games/epic-games-store/drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe" "-opengl -SkipBuildPatchPrereq"`

Optional (used mainly for protonfixes): `STORE`

  `WINEPREFIX=$HOME/Games/epic-games-store GAMEID=ulwgl-dauntless STORE=egs PROTONPATH="$HOME/.steam/steam/compatibilitytools.d/GE-Proton8-28" ./ulwgl-run "$HOME/Games/epic-games-store/drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe" "-opengl -SkipBuildPatchPrereq"`

# WHAT DOES THIS MEAN FOR OTHER LAUNCHERS (lutris/bottles/heroic/legendary,etc):

- everyone can use + contribute to the same protonfixes, no more managing individual install scripts per launcher
- everyone can run their games through proton just like a native steam game
- no steam or steam binaries required
- a unified online database of game fixes (protonfixes)

right now protonfixes packages a folder of 'gamefixes' however it could likely be recoded to pull from online quite easily

The idea is to get all of these tools using this same `ulwgl-run` and just feeding their envvars into it. That way any changes that need to happen can happen in proton-ge and/or protonfixes, or a 'unified proton' build based off GE, or whatever they want.

# WHAT IS THE BASIC PLAN OF PUTTING THIS INTO ACTION?

1. We build a database containing various game titles, their IDs from different stores, and their correlating ULWGL ID.
2. Various launchers then search the database to pull the ULWGL ID, and feed it as the game ID to ulwgl-run alongside the store type, proton version, wine prefix, game executable, and launch arguements.
3. When the game gets launched from ulwgl-run, protonfixes picks up the store type and ULWGL ID and finds the appropriate fix script for it, then applies it before running the game.
4. protonfixes has folders separated for each store type. The ULWGL ID for a game remains the exact same across multiple stores, the only difference being it can have store specific scripts OR it can just symlink to another existing script that already has the fixes it needs.

Example:

Borderlands 3 from EGS store.
1. Generally a launcher is going to know which store it is using already, so that is easy enough to determine and feed the STORE variable to the launcher.
2. To determine the game title, EGS has various codenames such as 'Catnip'. The launcher would see "ok store is egs and codename is Catnip, let's search the ULWGL database for those"
3. In our ULWGL unified database, we create a 'title' column, 'store' column, 'codename' column, 'ULWGL-ID' column. We add a line for Borderlands 3 and fill in the details for each column.
4. Now the launcher can search 'Catnip' and 'egs' as the codename and store in the database and correlate it with Borderlands 3 and ULWGL-12345. It can then feed ULWGL-12345 to the ulwgl-run script.


# Building and packaging:
Building ULWGL currently requires `bash`, `make` and `meson`

To build ULWGL, after downloading and extracting the source code from this repository, change into the newly extracted directory
```shell
cd ULWGL-Launcher
```

To configure the installation `PREFIX` (this is not related to wine's `WINEPREFIX`) use the `configure.sh` script
```shell
./configure.sh --prefix=/usr
```
Change the `--prefix` as fit for your distribution, for example `/usr/local`, or `/app` for packaging through flatpak

Then run `make` to build. After a successful build the resulting files should be available in the `./builddir` directory

## Installing 
To install ULWGL run the following command after completing the steps described above
```shell
make install
```
or if you are packaging ULWGL
```shell
make DESTDIR=<packaging_directory> install
```

## Installing as user
If you want to install ULWGL just for your user, or for quickly testing, you can configure ULWGL with the following command
```shell
./configure.sh --user-install
```
followed by 
```shell
make install
```
This will install ULWGL under `~/.local/share/ulwgl` and place the executable in `~/.local/bin`
You will need to add `$HOME/.local/bin` in your `$PATH` to be able to run ULWGL this way by exporting the path in your shell's configuration, for example `~/.bash_profile`
```shell
export PATH="$HOME/.local/bin:$PATH"
```


# Usage notes:  

When /usr/bin/ulwgl-run is first run, it will copy the /usr/share/ULWGL folder to ~/.local/share/ULWGL. From that point on the ~/.local/share/ULWGL folder will be used for running ulwgl. It will also perform a version check to make sure that if the contents of /usr/share/ULWGL are updated, that the local version also gets updated.  

When /usr/bin/ulwgl-run is first run, it also copies /usr/share/ULWGL/ULWGL-Runner to ~/.local/share/steam/compatibilitytools.d/ so that it can be used as a compatibility tool in steam for non-steam games the same way Proton is.  

When /usr/bin/ulwgl-run is run, if a PROTONPATH is not specified, it will automatically download and use ULWGL-Proton and place it at ~/.local/share/steam/compatibilitytools.d/  

When /usr/bin/ulwgl-run is run, if a WINEPREFIX is not specified, it will automatically create one using the ulwgl-id at ~/Games/ULWGL/<ulwgl-id>  

# README notes from Valve's steam-runtime-tools:

Steam Linux Runtime 3.0 (sniper)
================================

This container-based release of the Steam Runtime is used for native
Linux games, and for Proton 8.0+.

For general information please see
<https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/container-runtime.md>
and
<https://gitlab.steamos.cloud/steamrt/steamrt/-/blob/steamrt/sniper/README.md>

Release notes
-------------

Please see
<https://gitlab.steamos.cloud/steamrt/steamrt/-/wikis/Sniper-release-notes>

Known issues
------------

Please see
<https://github.com/ValveSoftware/steam-runtime/blob/master/doc/steamlinuxruntime-known-issues.md>

Reporting bugs
--------------

Please see
<https://github.com/ValveSoftware/steam-runtime/blob/master/doc/reporting-steamlinuxruntime-bugs.md>

Development and debugging
-------------------------

The runtime's behaviour can be changed by running the Steam client with
environment variables set.

`STEAM_LINUX_RUNTIME_LOG=1` will enable logging. Log files appear in
`SteamLinuxRuntime_sniper/var/slr-*.log`, with filenames containing the app ID.
`slr-latest.log` is a symbolic link to whichever one was created most
recently.

`STEAM_LINUX_RUNTIME_VERBOSE=1` produces more detailed log output,
either to a log file (if `STEAM_LINUX_RUNTIME_LOG=1` is also used) or to
the same place as `steam` output (otherwise).

`PRESSURE_VESSEL_SHELL=instead` runs an interactive shell in the
container instead of running the game.

Please see
<https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/distro-assumptions.md>
for details of assumptions made about the host operating system, and some
advice on debugging the container runtime on new Linux distributions.

Game developers who are interested in targeting this environment should
check the SDK documentation <https://gitlab.steamos.cloud/steamrt/sniper/sdk>
and general information for game developers
<https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/slr-for-game-developers.md>.

Licensing and copyright
-----------------------

The Steam Runtime contains many third-party software packages under
various open-source licenses.

For full source code, please see the version-numbered subdirectory of
<https://repo.steampowered.com/steamrt-images-sniper/snapshots/>
corresponding to the version numbers listed in VERSIONS.txt.
