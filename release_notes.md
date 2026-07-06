# 🎁 Release notes (`1.4.1`)

## Changes
- bump rpm spec sheet commit again
- bump release notes again
- bump runtime
- bump rpm spec sheet
- Bump version to 1.4.1
- bump release notes
- enable UMU_CONTAINER_NSENTER for e2e workflow
- Merge pull request #683 from loathingKernel/launcher-service
- Merge pull request #690 from GitXpresso/main
- Merge pull request #684 from majar5c/main
- Merge pull request #691 from Techbert08/fix-ge-proton-asset-count-arch
- fixup lint error
- Fix _fetch_releases() failing on releases with multiple architectures
- Updated: README.md  * "git clone --recurse-submodules https://github.com/Open-Wine-Components/umu-launcher" was added, so the compile process is successful
- fix: Fix format error in debug message
- Merge pull request #517 from SyntaxOverflow/patch-1
- Merge pull request #662 from nihaals/fix-x-window-id-reuse
- Merge pull request #429 from loathingKernel/xlib_print
- Merge pull request #643 from Open-Wine-Components/dependabot/cargo/sha2-0.11.0
- Merge pull request #679 from Open-Wine-Components/dependabot/cargo/pyo3-0.29.0
- Merge pull request #681 from Open-Wine-Components/dependabot/github_actions/actions/checkout-7
- Merge pull request #667 from nicholascw/main
- umu_run: gate launcher service behind `UMU_CONTAINER_NSENTER` env var.
- build(deps): bump actions/checkout from 6 to 7
- build(deps): bump pyo3 from 0.28.2 to 0.29.0
- lint: reorganize imports
- Merge pull request #650 from recreators01/https_proxy
- Merge pull request #674 from loathingKernel/phase-out-sniper-arm64
- umu: Remove arm64 sniper runtime
- fix umu-launcher#659
- fix: require explicit URL scheme when using ProxyManager
- feat: add support for https_proxy environment variable (#415)
- umu_run: handle re-used X window IDs
- Merge pull request #652 from loathingKernel/use_cdn
- umu_runtime: implement slightly smarter version comparison
- umu_runtime: don't avoid cloudflare CDN
- build(deps): bump sha2 from 0.10.9 to 0.11.0
- bump version to 1.4.0
- generate release notes for 1.4.0
- Merge pull request #636 from Open-Wine-Components/dependabot/github_actions/dtolnay/rust-toolchain-1.100
- Merge pull request #639 from Open-Wine-Components/copilot/sub-pr-636
- fix: use stable rust toolchain instead of pinned version
- Initial plan
- Merge pull request #638 from Open-Wine-Components/copilot/sub-pr-636
- fix(e2e): remove redundant hardcoded rustup version commands
- fix: update rustup toolchain version from 1.85 to 1.100 in e2e.yml
- Initial plan
- Merge pull request #632 from MattSturgeon/nix-versionCheckHook
- Merge pull request #637 from loathingKernel/revert_ld_preload
- umu_run: unset LD_PRELOAD only in gamescope session
- umu_utils: use contextmanager to redirect stdout to stderr
- Merge pull request #633 from loathingKernel/gated_reentry
- build(deps): bump dtolnay/rust-toolchain from 1.85 to 1.100
- umu_run: gate container re-enter behavior behind an explicit switch
- umu_run: replace token string values with ProtonVersion enumeration members
- umu_proton: add special case `umu-host` tool to satisfy `UMU_NO_PROTON=1` fallback
- build(nix): disable versionCheckHook specifically
- Merge pull request #631 from loathingKernel/setup_prefix
- Revert "umu_runtime: remove temporary entry point override"
- Create umu-launcher.desktop

## Metadata
```
This version -------- 1.4.1
Previous version ---- 1.4.0.rc3
Total commits ------- 60
```
