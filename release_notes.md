# 🎁 Release notes (`1.2.6`)

## Changes
- Merge pull request #426 from Open-Wine-Components/revert-410-unruntime
- Revert "umu_run: handle Protons without an explicit runtime requirement"
- bump release notes
- Merge pull request #408 from R1kaB3rN/bump-version-1.2.6
- Merge pull request #424 from Open-Wine-Components/fix/install-path
- Merge pull request #410 from loathingKernel/unruntime
- improv: default to environment provided STEAM_COMPAT_INSTALL_PATH
- umu: update tests
- umu_run: move toml config loading earlier and merge it with the environment
- build(deps): bump cachix/install-nix-action from 30 to 31 (#423)
- umu: update tests
- umu_run: extract function from `umu_run` to download proton if needed
- umu_run: raise exception if PROTONPATH doesn't exist while checking for runtime version
- umu_run: try to decouple get_umu_proton from check_env
- umu_run: handle Protons without an explicit runtime requirement
- Merge pull request #402 from MattSturgeon/nix/drop-old
- Merge pull request #413 from loathingKernel/isatty
- packaging: update umu-launcher debian packages (#422)
- deb: update rustup patch (#421)
- refactor: use __package__ to determine module (#420)
- feat: extend lint rules (#419)
- umu_log: do an early return if not tty
- umu_log: do not use colors if stderr is not an interactive terminal
- build(deps): bump pyo3 from 0.23.5 to 0.24.0 (#411)
- Bump version to 1.2.6
- fix: adhere to the XDG spec for compatibilitytools.d
- build: remove umu-launcher install from packaging
- build: remove umu-launcher build target
- Don't package and distrbute umu-launcher as a compatibility tool -- steam ends up using it on every launch (bug), and there's also not really any point
- build(nix): drop support for outdated nixpkgs revisions
- packaging/nix/flake.lock: Update (#406)
- build(deps): bump pyo3 from 0.23.4 to 0.23.5 (#405)
- refactor: update runtime directory structure (#400)
- Support overriding 1.2.0+ nix package (#374)
- bump commit on rpm spec sheet to match tag just in case of manual builds
- bump release notes for 1.2.5 (again)

## Metadata
```
This version -------- 1.2.6
Previous version ---- 1.2.5
Total commits ------- 36
```
