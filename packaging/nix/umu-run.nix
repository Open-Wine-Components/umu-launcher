{ package, buildFHSEnv, writeShellScript,version, ...}:
buildFHSEnv{
  name = "umu-run";
  version = "${version}";
  targetPkgs = pkgs: ([
    package
  ]);
  runScript = writeShellScript "umu-run-shell" ''
    ${package}/bin/umu "$@"
  '';
}
