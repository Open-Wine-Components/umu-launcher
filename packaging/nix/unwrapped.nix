{
  # Dependencies
  lib,
  rustPlatform,
  python3Packages,
  umu-launcher-unwrapped,
  lastModifiedDate,
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
    "python3Packages"
    "umu-launcher-unwrapped"
    "lastModifiedDate"
  ];

  # Use the in-tree version
  version = lib.pipe ../../umu/__init__.py [
    builtins.readFile
    (lib.splitString "\n")
    (map (lib.match ''^__version__ = "([^"]+)".*$''))
    (lib.findFirst lib.isList (throw "No version found in __init__.py"))
    builtins.head
  ];

  # Format date as YYYY-MM-DD
  date = lib.pipe lastModifiedDate [
    (lib.match "^([0-9]{4})([0-9]{2})([0-9]{2}).*$")
    (result: lib.throwIf (result == null) "umu-launcher-unwrapped: Invalid lastModifiedDate format: ${lastModifiedDate}" result)
    (lib.concatStringsSep "-")
  ];

  # Use the unwrapped package as-is or override it,
  # based on whether we have any override args
  package =
    if overrideArgs == {}
    then umu-launcher-unwrapped
    else umu-launcher-unwrapped.override overrideArgs;
in
  package.overridePythonAttrs (old: {
    version = "${version}-unstable-${date}";
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

    # versionCheckHook expects --version to print the entire package version
    # while the program is built using a PEP-440 version.
    # Strip the nixpkgs-format suffix during the versionCheckPhase.
    preVersionCheck = ''
      _version="$version"
      version="''${version%%-*}"
    '';

    postVersionCheck = ''
      version="$_version"
      unset _version
    '';
  })
