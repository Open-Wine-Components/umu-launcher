{
  # Dependencies
  callPackage,
  lib,
  rustPlatform,
  umu-launcher-unwrapped,
  version,
  # Freeform overrides
  ...
} @ args: let
  # Unknown args will be used to override the nixpkgs package
  # NOTE: All known args must be removed here
  overrideArgs = builtins.removeAttrs args [
    "callPackage"
    "lib"
    "rustPlatform"
    "umu-launcher-unwrapped"
    "version"
  ];

  # Remove unsupported args not accepted by old-unwrapped.nix
  oldVersionArgs = builtins.removeAttrs args [
    "callPackage"
    "version"
  ];

  # Figure out and/or override the base package
  package =
    # Nixpkgs bumped 1.1.4 -> 1.2.3 on 2025-02-17
    # https://github.com/NixOS/nixpkgs/pull/381975
    if lib.versionOlder umu-launcher-unwrapped.version "1.2.0"
    then callPackage ./old-unwrapped.nix oldVersionArgs
    # Use the unwrapped package as-is or override it,
    # based on whether we have any override args
    else if overrideArgs == {}
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
