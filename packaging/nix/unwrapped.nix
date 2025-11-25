{
  # Dependencies
  lib,
  rustPlatform,
  umu-launcher-unwrapped,
  version,
  # Freeform overrides
  ...
} @ args:
# Nixpkgs bumped 1.1.4 -> 1.2.5 on 2025-02-20
# Available in all unstable channels since 2025-02-24
# https://github.com/NixOS/nixpkgs/pull/381975
assert lib.assertMsg (lib.versionAtLeast umu-launcher-unwrapped.version "1.2.0") ''
  You have updated your umu-launcher input, however you have an outdated nixpkgs input. A nixpkgs input with umu-launcher 1.2.0+ is required.
  Please update your nixpkgs revision by running `nix flake lock --update-input nixpkgs` or `nix flake update`.
''; let
  # Unknown args will be used to override the nixpkgs package
  # NOTE: All known args must be removed here
  overrideArgs = builtins.removeAttrs args [
    "lib"
    "rustPlatform"
    "umu-launcher-unwrapped"
    "version"
  ];

  # Use the unwrapped package as-is or override it,
  # based on whether we have any override args
  package =
    if overrideArgs == {}
    then umu-launcher-unwrapped
    else umu-launcher-unwrapped.override overrideArgs;
in
  package.overridePythonAttrs {
    inherit version;
    src = ../../.;
    cargoDeps = rustPlatform.importCargoLock {
      lockFile = ../../Cargo.lock;
    };

    # Specify ourselves which tests are disabled
    disabledTests = [
      # Broken? Asserts that $STEAM_RUNTIME_LIBRARY_PATH is non-empty
      # Fails with AssertionError: '' is not true : Expected two elements in STEAM_RUNTIME_LIBRARY_PATHS
      "test_game_drive_empty"
      "test_game_drive_libpath_empty"

      # Broken? Tests parse_args with no options (./umu_run.py)
      # Fails with AssertionError: SystemExit not raised
      "test_parse_args_noopts"
    ];
  }
