{ package, buildFHSEnv, writeShellScript,version, ...}:
buildFHSEnv{
  name = "umu-run";
  version = "${version}";
  targetPkgs = pkgs: ([
    package
  ]);
  multiArch = true;
  runScript = writeShellScript "umu-run-shell" ''
    ${package}/bin/umu "$@"
  '';
}
