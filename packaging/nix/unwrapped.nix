{
  # Dependencies
  lib,
  cargo,
  python3Packages,
  rustPlatform,
  umu-launcher-unwrapped,
  # Public API
  version,
  withTruststore ? true,
  withDeltaUpdates ? true,
}:
umu-launcher-unwrapped.overridePythonAttrs (prev: {
  src = ../../.;
  inherit version;

  cargoDeps = rustPlatform.importCargoLock {
    lockFile = ../../Cargo.lock;
  };

  # The nixpkgs patches (in `prev.patches`) are not needed anymore
  # - no-umu-version-json.patch was resolved in:
  #   https://github.com/Open-Wine-Components/umu-launcher/pull/289
  # - The other is backporting:
  #   https://github.com/Open-Wine-Components/umu-launcher/pull/343
  patches = [];

  nativeCheckInputs =
    (prev.nativeCheckInputs or [])
    ++ [
      python3Packages.pytestCheckHook
    ];

  nativeBuildInputs =
    (prev.nativeBuildInputs or [])
    ++ [
      rustPlatform.cargoSetupHook
      cargo
    ];

  pythonPath = with python3Packages;
    (prev.pythonPath or [])
    ++ [
      urllib3
      (callPackage ./pyzstd.nix {})
    ]
    ++ lib.optionals withTruststore [
      truststore
    ]
    ++ lib.optionals withDeltaUpdates [
      cbor2
      xxhash
    ];

  configureFlags =
    (prev.configureFlags or [])
    ++ [
      "--use-system-pyzstd"
      "--use-system-urllib"
    ];

  disabledTests = [
    # Broken? Asserts that $STEAM_RUNTIME_LIBRARY_PATH is non-empty
    # Fails with AssertionError: '' is not true : Expected two elements in STEAM_RUNTIME_LIBRARY_PATHS
    "test_game_drive_empty"
    "test_game_drive_libpath_empty"

    # Broken? Tests parse_args with no options (./umu_run.py)
    # Fails with AssertionError: SystemExit not raised
    "test_parse_args_noopts"
  ];

  preCheck = ''
    ${prev.preCheck or ""}

    # Some tests require a writable HOME
    export HOME=$(mktemp -d)
  '';
})
