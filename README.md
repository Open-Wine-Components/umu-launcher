# umu
[![Github release](https://img.shields.io/github/v/release/Open-Wine-Components/umu-launcher)](https://github.com/Open-Wine-Components/umu-launcher/releases)
[![GPLv3 license](https://img.shields.io/github/license/Open-Wine-Components/umu-launcher)](https://github.com/Open-Wine-Components/umu-launcher/blob/main/LICENSE)
[![Actions status](https://github.com/Open-Wine-Components/umu-launcher/actions/workflows/umu-python.yml/badge.svg)](https://github.com/Open-Wine-Components/umu-launcher/actions)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?logo=discord&logoColor=white)](https://discord.com/invite/6y3BdzC)

## Description

### What is this?

This is a unified launcher for Windows games on Linux. It is essentially a copy of the [Steam Runtime Tools](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools) and [Steam Linux Runtime](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/container-runtime.md) that Valve uses for [Proton](https://github.com/ValveSoftware/Proton), with some modifications made so that it can be used outside of Steam.

### Why is it called UMU?

An umu is an above-ground oven of hot volcanic stones originating from Polynesian culture. After the stones are heated, the top layer is removed and the food placed on top to heat/cook. We chose the name because Valve's containerization tool is named pressure-vessel. We're "preparing" the pressure vessel similar to how you would use a stove top pressure-cooker -- by placing it on our umu's "stovetop"

### What does it do?

When Steam launches a Proton game, it launches it like this:

```
/home/tcrider/.local/share/Steam/ubuntu12_32/reaper SteamLaunch AppId=348550 -- /home/tcrider/.local/share/Steam/ubuntu12_32/steam-launch-wrapper -- /home/tcrider/.local/share/Steam/steamapps/common/SteamLinuxRuntime_sniper/_v2-entry-point --verb=waitforexitandrun -- /home/tcrider/.local/share/Steam/compatibilitytools.d/GE-Proton8-27/proton waitforexitandrun /home/tcrider/.local/share/Steam/steamapps/common/Guilty Gear XX Accent Core Plus R/GGXXACPR_Win.exe
```

We can ignore this `/home/tcrider/.local/share/Steam/ubuntu12_32/steam-launch-wrapper`, it's just a process runner with no real value other than forwarding environment variables (more on that later).

I managed to pull the environment variables it uses by making Steam run `printenv` for the game's command line. We needed these envvars because Proton expects them in order to function. With them we can essentially make Proton run without needing steam at all.

Next this part `/home/tcrider/.local/share/Steam/steamapps/common/SteamLinuxRuntime_sniper/_v2-entry-point`

The first part `/home/tcrider/.local/share/Steam/steamapps/common/SteamLinuxRuntime_sniper/` is steam-runtime-tools compiled and is used alongside the sniper runtime container used during Proton builds.

The second part `_v2-entry-point` is just a bash script which loads Proton into the container and runs the game.

So, umu is basically a copy paste of `SteamLinuxRuntime_sniper`, which is a compiled version of steam-runtime-tools. We've renamed `_v2-entry-point` to `umu` and added `umu-run` to replace `steam-launch-wrapper`.

When you use `umu-run` to run a game, it uses the specified `WINEPREFIX`, Proton version, executable, and arguments passed to it to run the game in Proton, inside Steam's runtime container JUST like if you were running the game through Steam, except now you're no longer limited to Steam's game library or forced to add the game to Steam's library. In fact, you don't even have to have Steam installed.

### How do I use it?

```
WINEPREFIX=$HOME/Games/epic-games-store GAMEID=umu-dauntless PROTONPATH="$HOME/.steam/steam/compatibilitytools.d/GE-Proton8-28" umu-run "$HOME/Games/epic-games-store/drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe" -opengl -SkipBuildPatchPrereq
```

Optionally, with `STORE` (used mainly for protonfixes):

```
WINEPREFIX=$HOME/Games/epic-games-store GAMEID=umu-dauntless STORE=egs PROTONPATH="$HOME/.steam/steam/compatibilitytools.d/GE-Proton8-28" umu-run "$HOME/Games/epic-games-store/drive_c/Program Files (x86)/Epic Games/Launcher/Portal/Binaries/Win32/EpicGamesLauncher.exe" -opengl -SkipBuildPatchPrereq
```

See the [documentation](https://github.com/Open-Wine-Components/umu-launcher/blob/main/docs/umu.1.scd) for more examples and the [project's wiki](https://github.com/Open-Wine-Components/umu-launcher/wiki/Frequently-asked-questions-(FAQ)) for Frequently Asked Questions.

**Note**: umu-launcher will automatically use and download the latest Steam Runtime that is required by Proton, and move its files to `$HOME/.local/share/umu`.

### What does this mean for other launchers (Lutris, Bottles, Heroic, Legendary, etc.)?

- Everyone can use + contribute to the same protonfixes, no more managing individual install scripts per launcher
- Everyone can run their games through Proton just like a native Steam game
- No Steam or Steam binaries required
- A unified online database of game fixes (protonfixes)

Right now protonfixes packages a folder of 'gamefixes' however it could likely be recoded to pull from online quite easily. The idea is to get all of these tools using this same `umu-run` and just feeding their envvars into it. That way any changes that need to happen can happen in proton-ge and/or protonfixes, or a 'unified proton' build based off GE, or whatever they want.

### What is the basic plan of putting this into action?

1. We build a database containing various game titles, their IDs from different stores, and their correlating umu ID.
2. Various launchers then search the database to pull the umu ID, and feed it as the game ID to `umu-run` alongside the store type, Proton version, wine prefix, game executable, and launch arguments.
3. When the game gets launched from `umu-run`, protonfixes picks up the store type and umu ID and finds the appropriate fix script for it, then applies it before running the game.
4. protonfixes has folders separated for each store type. The umu ID for a game remains the exact same across multiple stores, the only difference being it can have store specific scripts OR it can just symlink to another existing script that already has the fixes it needs.

Example:

Borderlands 3 from EGS store.
1. Generally a launcher is going to know which store it is using already, so that is easy enough to determine and feed the `STORE` variable to the launcher.
2. To determine the game title, EGS has various codenames such as 'Catnip'. The launcher would see "ok store is egs and codename is Catnip, let's search the umu database for those"
3. In our umu unified database, we create a 'title' column, 'store' column, 'codename' column, 'umu-ID' column. We add a line for Borderlands 3 and fill in the details for each column.
4. Now the launcher can search 'Catnip' and 'egs' as the codename and store in the database and correlate it with Borderlands 3 and umu-12345. It can then feed umu-12345 to the `umu-run` script.

## Building

Building umu-launcher currently requires `bash`, `make`, and `scdoc` for distribution, as well as the following Python build tools: [build](https://github.com/pypa/build), [hatchling](https://github.com/pypa/hatch), and [installer](https://github.com/pypa/installer).

To build umu-launcher, after downloading and extracting the source code from this repository, change into the newly extracted directory
```shell
cd umu-launcher
```

To configure the installation `PREFIX` (this is not related to wine's `WINEPREFIX`) use the `configure.sh` script
```shell
./configure.sh --prefix=/usr
```
Change the `--prefix` as fit for your distribution, for example `/usr/local`, or `/app` for packaging through Flatpak.

Then run `make` to build. After a successful build the resulting files should be available in the `./builddir` directory


## Installing 

To install umu-launcher run the following command after completing the steps described above
```shell
make install
```

Or if you are packaging umu-launcher
```shell
make DESTDIR=<packaging_directory> install
```

### Installing as user

Additionally, user installations are supported if desired.

First, configure the build for a user installation
```shell
./configure.sh --user-install
```

Then run `make` install
```shell
make install
```

**Note**: When installing as a user, this will place the executable `umu-run` in `$HOME/.local/bin`. You will need to add `$HOME/.local/bin` in your `$PATH` to be able to run umu-launcher this way by exporting the path in your shell's configuration, for example `$HOME/.bash_profile`
```shell
export PATH="$HOME/.local/bin:$PATH"
```

## Packaging

### Nobara
```shell
dnf install -y umu-launcher*.rpm
```

### Arch Linux (AUR)
[![Stable version badge](https://img.shields.io/aur/version/umu-launcher?style=flat&label=umu-launcher)](https://aur.archlinux.org/packages/umu-launcher)

### NixOS
If there is any problem with the flake feel free to open a bug report and tag any of the maintainers
> maintainers: @beh-10257

If you want to add umu-launcher as a flake add this to your inputs in `flake.nix`
```nix
  inputs = {
    umu= {
      url = "git+https://github.com/Open-Wine-Components/umu-launcher/?dir=packaging\/nix&submodules=1";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  }
```
and in your `configuration.nix`
```nix
{inputs, pkgs, ... }:
{
  environment.systemPackages = [  (inputs.umu.packages.${pkgs.system}.umu.override {version = "${inputs.umu.shortRev}";})  ];
}
```

## Contributing

Contributions are welcome and appreciated. To get started, install [ruff](https://github.com/astral-sh/ruff) from your distribution and enable [ruff server](https://github.com/astral-sh/ruff/blob/main/crates/ruff_server/README.md) in your editor.

# README notes from Valve's steam-runtime-tools

Steam Linux Runtime 3.0 (sniper)
================================

This container-based release of the Steam Runtime is used for native Linux games, and for Proton 8.0+.

See [container-runtime](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/container-runtime.md) for details and the [steamrt wiki](https://gitlab.steamos.cloud/steamrt/steamrt/-/wikis/home) for a list of container-based runtimes.

Release notes
-------------

<https://gitlab.steamos.cloud/steamrt/steamrt/-/wikis/Sniper-release-notes>

Known issues
------------

<https://github.com/ValveSoftware/steam-runtime/blob/master/doc/steamlinuxruntime-known-issues.md>

Reporting bugs
--------------

<https://github.com/ValveSoftware/steam-runtime/blob/master/doc/reporting-steamlinuxruntime-bugs.md>

Development and debugging
--------------

The runtime's behaviour can be changed by running the Steam client with environment variables set.

`STEAM_LINUX_RUNTIME_LOG=1` will enable logging. Log files appear in `SteamLinuxRuntime_sniper/var/slr-*.log`, with filenames containing the app ID. `slr-latest.log` is a symbolic link to whichever one was created most recently.

`STEAM_LINUX_RUNTIME_VERBOSE=1` produces more detailed log output, either to a log file (if `STEAM_LINUX_RUNTIME_LOG=1` is also used) or to the same place as `steam` output (otherwise).

`PRESSURE_VESSEL_SHELL=instead` runs an interactive shell in the container instead of running the game.

Please see [distribution assumptions](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/distro-assumptions.md) for details of assumptions made about the host operating system, and some advice on debugging the container runtime on new Linux distributions.

Game developers who are interested in targeting this environment should check the [SDK documentation](https://gitlab.steamos.cloud/steamrt/sniper/sdk) and [general information for game developers](https://gitlab.steamos.cloud/steamrt/steam-runtime-tools/-/blob/main/docs/slr-for-game-developers.md).

Licensing and copyright
--------------

The Steam Runtime contains many third-party software packages under various open-source licenses.

For full source code, please see the [version-numbered subdirectory](https://repo.steampowered.com/steamrt-images-sniper/snapshots) corresponding to the version numbers listed in `VERSIONS.txt`.
