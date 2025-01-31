# From https://github.com/NixOS/nixpkgs/pull/365111
{
  buildPythonPackage,
  fetchFromGitHub,
  pkgs,
  pypaInstallHook,
  setuptoolsBuildHook,
}:
buildPythonPackage rec {
  pname = "pyzstd";
  version = "0.16.2";
  # There is a pyproject.toml, but we want to dynamically link zstd, which can
  # only be done through a setup.py argument
  pyproject = false;

  src = fetchFromGitHub {
    owner = "Rogdham";
    repo = "pyzstd";
    tag = version;
    hash = "sha256-Az+0m1XUFxExBZK8bcjK54Zt2d5ZlAKRMZRdr7rPcss=";
  };

  nativeBuildInputs = [
    pypaInstallHook
    setuptoolsBuildHook
  ];

  buildInputs = [
    pkgs.zstd
  ];

  setupPyBuildFlags = [
    "--dynamic-link-zstd"
  ];
}
