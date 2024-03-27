{ env, package, symlinkJoin }:
symlinkJoin {
  name = "yes";
  paths = [
    env
    package
  ];
  postBuild = ''
    rm $out/bin/umu-run
    echo hi
  '';
}
