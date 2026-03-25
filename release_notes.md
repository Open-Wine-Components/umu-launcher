# 🎁 Release notes (`1.4.0.rc3`)

## Changes
- Merge pull request #630 from loathingKernel/setup_prefix
- umu_run: remove `UMU-Proton` from the accepted tool tokens
- When UMU_NO_PROTON is set, run the 'required runtime' tool of the requested tool.
- umu_run: create pfx.lock in the compat_data folder instead of umu's folder
- fixup broken version check for nix
- bump nix flake
- fixup missing parenthesis
- Merge pull request #575 from MattSturgeon/update-nix
- Merge branch 'main' into update-nix
- Merge pull request #588 from Open-Wine-Components/dependabot/cargo/base16ct-1.0.0
- Merge pull request #629 from Open-Wine-Components/copilot/sub-pr-588-another-one
- Fix nix flake: support aarch64-linux with unwrapped package only
- Fix nix workflow: limit platforms to x86_64-linux, disable version check
- Initial plan
- Merge pull request #628 from Open-Wine-Components/copilot/sub-pr-588-again
- Update nixpkgs flake.lock to fix Nix flake build failure with base16ct 1.0.0
- Initial plan
- Merge pull request #627 from Open-Wine-Components/copilot/sub-pr-588
- Bump Rust/Cargo toolchain from 1.83 to 1.85 to support base16ct 1.0.0
- Revert base16ct from 1.0.0 to 0.2.0 to fix CI failures
- Initial plan
- build(deps): bump base16ct from 0.2.0 to 1.0.0
- Merge pull request #610 from Open-Wine-Components/dependabot/cargo/pyo3-0.28.2
- Enhance Rust setup in GitHub Actions workflow
- Merge pull request #626 from Open-Wine-Components/copilot/sub-pr-610-yet-again
- ci: fix default rust toolchain in e2e workflow
- Initial plan
- Merge pull request #625 from Open-Wine-Components/copilot/sub-pr-610-another-one
- ci: fix e2e cargo failure by passing PATH to sudo make install
- Initial plan
- Merge pull request #624 from Open-Wine-Components/copilot/sub-pr-610-again
- ci: add explicit Rust 1.83 toolchain setup to all workflows
- Initial plan
- build(deps): bump pyo3 from 0.25.1 to 0.28.2
- bump cargo to use rust 1.83
- bump deb patch to 1.83
- Merge pull request #616 from Open-Wine-Components/dependabot/github_actions/actions/download-artifact-8
- build(deps): bump actions/download-artifact from 7 to 8
- build(nix): build using PEP-440 "unstable" versioning
- build(nix): add workaround for versionCheckHook
- build(nix): Use nixpkgs compliant versioning
- build(nix): update flake inputs
- build(nix): configure commit summary

## Metadata
```
This version -------- 1.4.0.rc3
Previous version ---- 1.4.0.rc2
Total commits ------- 43
```
