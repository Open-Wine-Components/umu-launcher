{
  description = "umu universal game launcher";

  inputs = {
    nixpkgs = {
      type = "github";
      owner = "NixOS";
      repo = "nixpkgs";
      ref = "nixpkgs-unstable";
    };
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    umu-launcher-src = builtins.toPath "${self}/../../";

    pkgs = import nixpkgs {
      system = "x86_64-linux";
      overlays = [self.overlays.default];
    };

    version = "1.1.4";
  in {
    overlays.default = final: prev: let
      py = prev.python3;
    in {
      umu-launcher = final.callPackage ./umu-launcher.nix {
        inherit version;
        umu-launcher = umu-launcher-src;
        pyth1 = py;
      };

      umu-run = final.callPackage ./umu-run.nix {
        inherit version;
        package = final.umu-launcher;
      };

      umu = final.callPackage ./combine.nix {
        inherit version;
        env = final.umu-run;
        package = final.umu-launcher;
        truststore = true;
        cbor2 = true;
      };
    };

    packages.x86_64-linux = {
      inherit (pkgs) umu;
      default = self.packages.x86_64-linux.umu;
    };
  };
}
