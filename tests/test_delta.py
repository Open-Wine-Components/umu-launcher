#!/usr/bin/env python3

import json
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

import cbor2


def main():  # noqa: D103
    url = (
        "https://api.github.com/repos/Open-Wine-Components/umu-mkpatch/releases/latest"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "",
    }
    codename = "UMU-Latest"

    with urlopen(  # noqa: S310
        Request(url, headers=headers),  # noqa: S310
        context=ssl.create_default_context(),
    ) as resp:
        releases = json.loads(resp.read())
        for release in releases["assets"]:
            if not release["name"].endswith("cbor"):
                continue
            if release["name"].startswith(codename):
                durl = release["browser_download_url"]
                break

    with urlopen(durl) as resp:  # noqa: S310
        patch = cbor2.loads(resp.read())
        version = patch.get("contents")[0].get("source")

    url = f"https://github.com/Open-Wine-Components/umu-proton/releases/download/{version}/{version}.tar.gz"
    with urlopen(url) as resp:  # noqa: S310
        buffer = bytearray(64 * 1024)
        view = memoryview(buffer)
        with tempfile.NamedTemporaryFile(mode="ab+", buffering=0) as file:
            while size := resp.readinto(buffer):
                file.write(view[:size])
            cache = Path.home().joinpath(".cache", "umu")
            cache.mkdir(parents=True, exist_ok=True)
            file.seek(0)
            cache.joinpath(f"{version}.tar.gz").write_bytes(file.read())

    with tarfile.open(cache.joinpath(f"{version}.tar.gz")) as tar:
        tar.extraction_filter = tarfile.tar_filter
        tar.extractall(path=cache)  # noqa: S202
        compat = Path.home().joinpath(".local", "share", "umu", "compatibilitytools")
        compat.mkdir(parents=True, exist_ok=True)
        shutil.move(cache.joinpath(version), compat)
        compat.joinpath(version).rename(compat.joinpath("UMU-Latest"))

    exe = shutil.which("umu-run", path="/usr/local/bin")
    if exe is None:
        return 1

    return subprocess.run(
        (exe, "wineboot", "-u"),
        env={"PROTONPATH": "UMU-Latest", "GAMEID": "umu-0", "UMU_LOG": "1"},
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
