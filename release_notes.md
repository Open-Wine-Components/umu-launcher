# 🎁 Release notes (`1.2.3`)

## Changes
- bump 1.2.3 (fix fedora builds)
- small fixup for rpm spec sheet future proofing
- log when GAMEID is not set
- auto-set GAMEID=umu-default if no GAMEID is set -- one less envvar to cause user errors/headache
- fixup dependencies in rpm build and prep for native urllib3 when fedora moves 1.26->2.3 (fixes #376)
- dont set upper limit on urllib3 and pyzstd versions
- fedora ignores build options and still checks pyproject.toml, and it ships urllib3 so this check fails. fix it
- bump release notes

## Metadata
```
This version -------- 1.2.3
Previous version ---- 1.2.2
Total commits ------- 8
```
