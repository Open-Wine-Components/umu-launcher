# 🎁 Release notes (`1.2.4`)

## Changes
- bump 1.2.4
- Merge pull request #384 from MattSturgeon/nix/small-fixes
- update README
- update README
- Merge pull request #378 from Tiagoquix/docs-gameid
- build: require libzstd1 for deb (#391)
- Revert "Add support for Proton logging to stdout (#279)" (#390)
- build: create debian 13 package (#389)
- build(nix): run tests during check phase
- build(nix): minor fixes
- test: omit GAMEID in first install test
- test: fix tmp being created in project dir
- test: fix check_env tests (#383)
- Merge pull request #382 from Open-Wine-Components/workflow_VERSION_fixup
- always use latest tag for version to avoid workflow micro versioning
- Merge pull request #379 from Open-Wine-Components/rpm_fixup
- we have to do some workflow stupidity until fedora bumps urllib3
- don't get VERSION from git in makefile, sometimes we build from tarball only. sed the version into makefile during workflow
- always set a default tag in rpm sheet
- let's verify the tags and make sure the fetch depth is 0
- let's try forc grabbing the version and commit
- dont build from git in srpm
- lets try checking out the source before we copy it
- cant grab a tag from git if you're not inside a git repo dummy
- fix broken sed command
- echo the shasum we're using
- handle whitespace better and print manual_commit value
- oops, forgot to fix shortcommit
- lets try disabling manual_commit by default instead of setting it empty
- more rpm spec sheet cleanup
- we still need to set manual commit to make sure latest dev build gets built if its past a release
- git wizardry fixup
- some git wizardry
- use tag as version in rpm spec
- Update docs for version 1.2.3
- use globals for tag and manual_commit in rpm spec
- fixup dev build invalid version failure
- bump release notes

## Metadata
```
This version -------- 1.2.4
Previous version ---- 1.2.3
Total commits ------- 38
```
