{ env, package, symlinkJoin,version,truststore }:
symlinkJoin {
  name = "umu-run-bwrap";
  paths = [
    (package.override {version = "${version}";truststore = truststore;})
    (env.override {version = "${version}";})
  ];
  postBuild = ''
    rm $out/bin/umu
  '';
}
