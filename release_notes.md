# 🎁 Release notes (`1.2.7`)

## Changes
- docs: remove mentions GE-Latest and UMU-Latest from docs
- refactor: use original SteamGameId for window management
- Revert "don't set SteamGameId if it's already set by steam"
- fix: skip unlinking UMU-Latest in compatibilitytools.d (#504)
- refactor: prefer cache over lru_cache
- chore: update format
- refactor: use value from VERSION.txt for runtime updates (#503)
- refactor: use tmpfs when sufficiently large (#502)
- fix: create temporary directory on subsequent network errors (#501)
- only run in steammode when running in a flatpak container (#496)
- chore: extend lint rules (#494)
- derive steam_appid from SteamGameId (#491)
- refactor: improve subprocess PID detection for window management (#493)
- ci: add noqa for SteamGameId
- Merge pull request #447 from nodscher/main
- build(deps): bump pyo3 from 0.25.0 to 0.25.1 (#488)
- refactor: remove fallback to XRes when acquiring window PIDs (#484)
- chore: remove unused window management functionality (#483)
- build(deps): bump DeterminateSystems/flake-checker-action from 9 to 10 (#482)
- fix: set STEAM_GAME property for initial X windows (#478)
- fix: update log statements (#477)
- fix: update window management for Flatpak apps in Steam mode (#474)
- build(deps): bump pyo3 from 0.24.2 to 0.25.0 (#464)
- test: find the expected source in delta update test (#461)
- fix: downgrade pyzstd 0.17.0 -> 0.16.2 (#462)
- fix: dynamically link to zstd when vendoring (#458)
- chore: bump subprojects (#457)
- build(deps): bump sha2 from 0.10.8 to 0.10.9 (#449)
- don't set SteamGameId if it's already set by steam
- build(deps): bump pyo3 from 0.24.1 to 0.24.2 (#442)
- build(deps): bump pyo3 from 0.24.0 to 0.24.1 (#433)
- bump release notes

## Metadata
```
This version -------- 1.2.7
Previous version ---- 1.2.6
Total commits ------- 32
```
