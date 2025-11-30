{
  description = "umu universal game launcher";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  nixConfig = {
    commit-lock-file-summary = "build(nix): update flake inputs";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    inherit (nixpkgs) lib;

    # Utility function for producing consistent rename warning messages
    rename = old: new: lib.warn "`${old}` has been renamed to `${new}`";

    # Supported platforms & package sets
    platforms = lib.platforms.linux;
    supportedPkgs = lib.filterAttrs (system: _: builtins.elem system platforms) nixpkgs.legacyPackages;
  in {
    overlays.default = final: prev: {
      umu-launcher = final.callPackage ./package.nix {
        inherit (prev) umu-launcher;
      };
      umu-launcher-unwrapped = final.callPackage ./unwrapped.nix {
        inherit (prev) umu-launcher-unwrapped;
        inherit (self) lastModifiedDate;
      };
      # Deprecated in https://github.com/Open-Wine-Components/umu-launcher/pull/345 (2025-01-31)
      umu = rename "umu" "umu-launcher" final.umu-launcher;
      umu-run = rename "umu-run" "umu-launcher" final.umu-launcher;
    };

    formatter = builtins.mapAttrs (system: pkgs: pkgs.alejandra) nixpkgs.legacyPackages;

    packages =
      builtins.mapAttrs (system: pkgs: rec {
        default = umu-launcher;
        inherit
          (pkgs.extend self.overlays.default)
          umu-launcher
          umu-launcher-unwrapped
          ;
        # Deprecated in https://github.com/Open-Wine-Components/umu-launcher/pull/345 (2025-01-31)
        umu = rename "packages.${system}.umu" "packages.${system}.umu-launcher" umu-launcher;
      })
      supportedPkgs;
  };
}
