{ env, package, symlinkJoin }:
symlinkJoin {
  name = "umu-run-bwrap";
  paths = [
    env
    package
  ];
  postBuild = ''
    rm $out/bin/umu
  '';
}
