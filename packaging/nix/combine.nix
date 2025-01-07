{
  env,
  package,
  symlinkJoin,
  version,
  truststore,
  cbor2,
}:
symlinkJoin {
  name = "umu-run-bwrap";
  paths = [
    (package.override {
      version = "${version}";
      truststore = truststore;
      cbor2 = cbor2;
    })
    (env.override {version = "${version}";})
  ];
  postBuild = ''
    rm $out/bin/umu
  '';
}
