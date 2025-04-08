{
  # Dependencies
  callPackage,
  lib,
  rustPlatform,
  python3Packages,
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
    "python3Packages"
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
  package.overridePythonAttrs (old: {
    inherit version;
    src = ../../.;
    cargoDeps = rustPlatform.importCargoLock {
      lockFile = ../../Cargo.lock;
    };

    pythonPath =
      (old.pythonPath or [])
      ++ [
        python3Packages.vdf
      ];

    configureFlags =
      (old.configureFlags or [])
      ++ [
        "--use-system-vdf"
      ];

    # Specify ourselves which tests are disabled
    disabledTests = [
      # Broken? Asserts that $STEAM_RUNTIME_LIBRARY_PATH is non-empty
      # Fails with AssertionError: '' is not true : Expected two elements in STEAM_RUNTIME_LIBRARY_PATHS
      "test_game_drive_empty"
      "test_game_drive_libpath_empty"

      # Broken? Tests parse_args with no options (./umu_run.py)
      # Fails with AssertionError: SystemExit not raised
      "test_parse_args_noopts"

      # FileNotFoundError: [Errno 2] No such file or directory: .local/share/umu/toolmanifest.vdf
      "test_build_command"
      "test_build_command_linux_exe"
      "test_build_command_nopv"

      # TypeError: cannot unpack non-iterable ThreadPoolExecutor object
      "test_env_nowine_noproton"
      "test_env_wine_noproton"
    ];
  })
