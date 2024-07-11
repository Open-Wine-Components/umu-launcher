{
  description = "umu universal game launcher";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };
  outputs = { self, nixpkgs }:
  let
  umu-launcher-src=builtins.toPath "${self}/../../";
  nixpk=nixpkgs.legacyPackages.x86_64-linux;
  in
  let
  pyth = nixpk.pkgs.python3;
  in
  let
    umu-package = nixpk.callPackage ./umu-launcher.nix { umu-launcher=umu-launcher-src; pyth1=pyth; };
    umu-run = nixpk.callPackage ./umu-run.nix { package=umu-package; };
  in{
    packages.x86_64-linux.umu = nixpk.callPackage ./combine.nix { env=umu-run; package=umu-package; };
  };
}
