{pyth1 ,python3Packages , umu-launcher, pkgs, ...}:
python3Packages.buildPythonPackage {
  name = "umu-launcher";
  version = "1.1.3";
  src = umu-launcher;
  pyproject = false;
  depsBuildBuild = [
    pkgs.meson
    pkgs.ninja
    pkgs.scdoc
    pkgs.git
    pkgs.python3Packages.installer
    (pkgs.hatch.overrideAttrs (prev: {
      disabledTests = prev.disabledTests ++ [
        "test_field_readme"
        "test_field_string"
        "test_field_complex"
        "test_plugin_dependencies_unmet"
      ];
    }))
    pkgs.python3Packages.build
  ];
  propagatedBuildInputs = [
    pyth1
    pkgs.python3Packages.xlib
    pkgs.python3Packages.filelock
  ];
  makeFlags = [ "PYTHON_INTERPRETER=${pyth1}/bin/python" "SHELL_INTERPRETER=/run/current-system/sw/bin/bash" "DESTDIR=${placeholder "out"}" ];
  dontUseMesonConfigure = true;
  dontUseNinjaBuild = true;
  dontUseNinjaInstall = true;
  dontUseNinjaCheck = true;
  configureScript = "./configure.sh";
  configureFlags = [ "--prefix=${placeholder "out"}" ];
  postInstall=''
    mv -fv $out${pyth1}/* $out
    mv -fv $out$out/* $out
    rm -vrf $out/nix
    mv $out/bin/umu-run $out/bin/umu
  '';
}
