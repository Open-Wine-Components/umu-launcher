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
  ...
} @ args: let
  # Nixpkgs bumped 1.1.4 -> 1.2.1 on 2025-02-14
  # https://github.com/NixOS/nixpkgs/pull/381975
  isOldVersion = lib.versionOlder umu-launcher-unwrapped.version "1.2.0";

  # Unknown args will be used to override the nixpkgs package
  overrides = builtins.removeAttrs args [
    "lib"
    "cargo"
    "python3Packages"
    "rustPlatform"
    "umu-launcher-unwrapped"
    "version"
  ];

  package =
    if isOldVersion || overrides == {}
    then umu-launcher-unwrapped
    else umu-launcher-unwrapped.override overrides;
in
  package.overridePythonAttrs (prev: (
    {
      src = ../../.;
      inherit version;
      cargoDeps = rustPlatform.importCargoLock {
        lockFile = ../../Cargo.lock;
      };
    }
    # These overrides were only needed before 1.2.0
    // lib.optionalAttrs isOldVersion {
      # The nixpkgs patches (in `prev.patches`) are not needed anymore
      # - no-umu-version-json.patch was resolved in:
      #   https://github.com/Open-Wine-Components/umu-launcher/pull/289
      # - The other is backporting:
      #   https://github.com/Open-Wine-Components/umu-launcher/pull/343
      patches = [];

      configureFlags = [
        "--use-system-pyzstd"
        "--use-system-urllib"
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
    }
  ))
