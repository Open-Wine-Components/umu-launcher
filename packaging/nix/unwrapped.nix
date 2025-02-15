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
})
