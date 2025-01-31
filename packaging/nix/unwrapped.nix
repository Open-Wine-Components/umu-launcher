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

  # The nixpkgs patches (in `prev.patches`) are not needed anymore
  # - no-umu-version-json.patch was resolved in:
  #   https://github.com/Open-Wine-Components/umu-launcher/pull/289
  # - The other is backporting:
  #   https://github.com/Open-Wine-Components/umu-launcher/pull/343
  patches = [];

  # The `umu-vendored` target needs submodules. However, we don't actually need
  # this target or those submodules anyway, since we add `pyzstd` as a nix package
  #
  # As a temporary solution, we explicitly specify the supported build targets:
  buildFlags =
    (prev.buildFlags or [])
    ++ [
      "umu-dist"
      "umu-launcher"
    ];

  # Same issue for install targets
  installTargets =
    (prev.installTargets or [])
    ++ [
      "umu-dist"
      "umu-docs"
      "umu-launcher"
      "umu-delta"
      "umu-install"
      "umu-launcher-install"
      "umu-delta-install"
    ];

  nativeBuildInputs =
    (prev.nativeBuildInputs or [])
    ++ [
      rustPlatform.cargoSetupHook
      cargo
    ];

  propagatedBuildInputs =
    (prev.propagatedBuildInputs or [])
    ++ [
      python3Packages.urllib3
    ]
    ++ lib.optionals withTruststore [
      python3Packages.truststore
    ]
    ++ lib.optionals withDeltaUpdates [
      python3Packages.cbor2
      python3Packages.xxhash
      (python3Packages.callPackage ./pyzstd.nix {})
    ];

  cargoDeps = rustPlatform.importCargoLock {
    lockFile = ../../Cargo.lock;
  };
})
