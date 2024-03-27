{
  description = "umu universal game launcher";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    umu-launcher = {
      flake = false;
      #url="git+https://github.com/Open-Wine-Components/umu-launcher?submodules=1";
      url="path:../../";
    };
  };
  outputs = { self, nixpkgs, umu-launcher }:
  let
    umu-package = nixpkgs.legacyPackages.x86_64-linux.callPackage ./umu-launcher.nix { umu-launcher=umu-launcher; };
  in
  let
    umu-run = nixpkgs.legacyPackages.x86_64-linux.callPackage ./umu-run.nix { package=umu-package; };
  in{
    packages.x86_64-linux.umu = nixpkgs.legacyPackages.x86_64-linux.callPackage ./combine.nix { env=umu-run; package=umu-package; };
    packages.x86_64-linux.umu-launcher = umu-package;
  };
}
