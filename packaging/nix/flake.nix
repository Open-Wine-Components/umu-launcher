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
    # Both x86_64-linux and aarch64-linux are supported. On x86_64, the full
    # steam FHS wrapper (including i686 multilib) is exposed. On aarch64, only
    # the unwrapped package is available since the steam wrapper requires
    # 32-bit (i686) multilib which is x86-only.
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
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
      builtins.mapAttrs (system: pkgs:
        let
          extended = pkgs.extend self.overlays.default;
        in
        if system == "x86_64-linux" then rec {
          # On x86_64: expose the full steam FHS wrapper (includes i686 multilib
          # for running both 64-bit and 32-bit Windows games via Proton).
          default = umu-launcher;
          inherit (extended) umu-launcher umu-launcher-unwrapped;
          # Deprecated in https://github.com/Open-Wine-Components/umu-launcher/pull/345 (2025-01-31)
          umu = rename "packages.${system}.umu" "packages.${system}.umu-launcher" umu-launcher;
        } else rec {
          # On aarch64 (and other non-x86 Linux): only expose the unwrapped package.
          # The steam FHS wrapper needs glibc_multi (i686 multilib) which is x86-only.
          # On aarch64, umu-launcher-unwrapped runs against the arm64 steam runtime directly.
          default = umu-launcher-unwrapped;
          inherit (extended) umu-launcher-unwrapped;
        })
      supportedPkgs;
  };
}
