# 🎁 Release notes (`1.3.0`)

## Changes
- Merge pull request #570 from R1kaB3rN/bump-version-1.3.0
- Bump version to 1.3.0
- feat: add steamrt4 app id (#569)
- feat: add steamrt4 container runtime (#480)
- test: add tests when resolving required runtime (#568)
- ci: add fedora 43 workflow (#566)
- build(deps): bump actions/upload-artifact from 4 to 5 (#561)
- build(deps): bump actions/download-artifact from 5 to 6 (#562)
- refactor: update log statement on network error when downloading runtime
- fix: handle all network errors on proton download
- feat: add support for overriding default HTTP retries and timeouts (#560)
- ci: fix syntax in file lock test (#555)
- refactor: use XDG_DATA_HOME and delay temp cleanup at runtime install (#554)
- fix: ensure link and shim creation on runtime update (#553)
- fix: skip removing old runtime after updating
- refactor: prefer atomic syscalls when installing runtime (#550)
- ci: test against python 3.14 (#547)
- build(deps): bump actions/setup-python from 5 to 6 (#542)
- docs: update README.md. NixOS 25.05 is out (#541)
- fix: search /sbin for ldconfig (#540)
- build(deps): bump actions/checkout from 4 to 5 (#533)
- build(deps): bump actions/download-artifact from 4 to 5 (#530)
- chore: bump urllib3 to 2.5.0 (#528)
- build: fix FileNotFound in Debian 12 build (#529)
- build: drop filelock dependency in rpm (#527)
- ci: use Fedora 42 image for *.fc42.rpm (#526)
- refactor: improve logging on network error (#525)
- build(deps): bump DeterminateSystems/flake-checker-action from 11 to 12 (#518)
- fix: update output path when using zenity (#513)

## Metadata
```
This version -------- 1.3.0
Previous version ---- 1.2.9
Total commits ------- 29
```
