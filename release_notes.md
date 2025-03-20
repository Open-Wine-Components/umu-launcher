# 🎁 Release notes (`1.2.6`)

## Changes
- packaging: update umu-launcher debian packages (#422)
- deb: update rustup patch (#421)
- refactor: use __package__ to determine module (#420)
- feat: extend lint rules (#419)
- build(deps): bump pyo3 from 0.23.5 to 0.24.0 (#411)
- fix: adhere to the XDG spec for compatibilitytools.d
- build: remove umu-launcher install from packaging
- build: remove umu-launcher build target
- Don't package and distrbute umu-launcher as a compatibility tool -- steam ends up using it on every launch (bug), and there's also not really any point
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
Total commits ------- 15
```
