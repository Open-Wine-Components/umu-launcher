{
  # Dependencies
  lib,
  umu-launcher,
  umu-launcher-unwrapped,
  # Public API
  version ? null,
  withTruststore ? args.truststore or true,
  withDeltaUpdates ? true,
  # Freeform args
  ...
} @ args: let
  # Args not handled here; to be passed to the nixpkgs package
  # E.g. to support overriding `extraPkgs` or `extraLibraries`
  # NOTE: All known args must be removed here
  unknownArgs = builtins.removeAttrs args [
    "lib"
    "umu-launcher"
    "umu-launcher-unwrapped"
    "version"
    "withTruststore"
    "withDeltaUpdates"
    "truststore"
    "cbor2"
  ];

  # Overrides for umu-launcher-unwrapped
  overrides =
    # Warnings added in https://github.com/Open-Wine-Components/umu-launcher/pull/345 (2025-01-31)
    lib.warnIf (args ? truststore) "umu-launcher: the argument `truststore` has been renamed to `withTruststore`."
    lib.warnIf (args ? cbor2) "umu-launcher: the argument `cbor2` has never had any effect. The new argument `withDeltaUpdates` should be used instead."
    lib.warnIf (version == umu-launcher-unwrapped.version) "umu-launcher: the argument `version` is no longer necessary. The version now uses `shortRev` by default."
    lib.optionalAttrs (args ? version) {inherit version;}
    // lib.optionalAttrs (args ? withTruststore || args ? truststore) {inherit withTruststore;}
    // lib.optionalAttrs (args ? withDeltaUpdates) {inherit withDeltaUpdates;};
in
  umu-launcher.override (
    unknownArgs
    // {
      umu-launcher-unwrapped =
        if overrides == {}
        then umu-launcher-unwrapped
        else umu-launcher-unwrapped.override overrides;
    }
  )
