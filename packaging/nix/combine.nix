{ env, package, symlinkJoin,version }:
symlinkJoin {
  name = "umu-run-bwrap";
  paths = [
    (package.override {version = "${version}";})
    (env.override {version = "${version}";})
  ];
  postBuild = ''
    rm $out/bin/umu
  '';
}
