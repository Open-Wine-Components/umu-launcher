{
  lib,
  pyth1,
  python3Packages,
  umu-launcher,
  pkgs,
  version,
  truststore ? true,
  deltaUpdates ? {
    cbor2 = true;
    xxhash = true;
    zstd = true;
  },
  rustPlatform,
  ...
}:
python3Packages.buildPythonPackage {
  pname = "umu-launcher";
  version = "${version}";
  src = umu-launcher;
  patches = [./0-Makefile-no-vendor.patch];
  pyproject = false;
  depsBuildBuild = [
    pkgs.meson
    pkgs.ninja
    pkgs.scdoc
    pkgs.git
    pkgs.python3Packages.installer
    # temporary fix, tracking https://github.com/NixOS/nixpkgs/issues/366359
    (pkgs.hatch.overridePythonAttrs {doCheck = false;})
    pkgs.python3Packages.build
    pkgs.cargo
  ];
  cargoDeps = rustPlatform.importCargoLock {
    lockFile = ../../Cargo.lock;
  };
  nativeBuildInputs = with rustPlatform; [cargoSetupHook];
  propagatedBuildInputs =
    [
      pyth1
      pkgs.bubblewrap
      pkgs.python3Packages.xlib
      pkgs.python3Packages.urllib3
    ]
    ++ lib.optional truststore pkgs.python3Packages.truststore
    ++ lib.optional deltaUpdates.cbor2 pkgs.python3Packages.cbor2
    ++ lib.optional deltaUpdates.xxhash pkgs.python3Packages.xxhash
    ++ lib.optional deltaUpdates.zstd pkgs.zstd;
  makeFlags = ["PYTHON_INTERPRETER=${pyth1}/bin/python" "SHELL_INTERPRETER=/run/current-system/sw/bin/bash" "DESTDIR=${placeholder "out"}"];
  dontUseMesonConfigure = true;
  dontUseNinjaBuild = true;
  dontUseNinjaInstall = true;
  dontUseNinjaCheck = true;
  configureScript = "./configure.sh";
  configureFlags = ["--prefix=${placeholder "out"}"];
  postInstall = ''
    mv -fv $out${pyth1}/* $out
    mv -fv $out$out/* $out
    rm -vrf $out/nix
    mv $out/bin/umu-run $out/bin/umu
  '';
}
