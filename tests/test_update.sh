#!/usr/bin/env sh

mkdir -p $HOME/.local/share/umu

curl -LJO "https://repo.steampowered.com/steamrt3/images/0.20240916.101795/SteamLinuxRuntime_sniper.tar.xz"
tar xaf SteamLinuxRuntime_sniper.tar.xz .
mv SteamLinuxRuntime_sniper/* $HOME/.local/share/umu
mv $HOME/.local/share/umu/_v2-entry-point $HOME/.local/share/umu/umu

UMU_LOG=debug GAMEID=umu-0 umu-run wineboot -u
