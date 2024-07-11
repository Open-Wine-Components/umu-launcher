{ package, buildFHSEnv, writeShellScript, ...}:
buildFHSEnv {
  name = "umu-run";
  runScript = writeShellScript "umu-run-shell" ''
    ${package}/bin/umu "$@"
  '';
}
