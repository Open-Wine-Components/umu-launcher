#!/usr/bin/env python3

import json
import os
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
    ctx = ssl.create_default_context()

    durl = ""
    with urlopen(  # noqa: S310
        Request(url, headers=headers),  # noqa: S310
        context=ctx,
    ) as resp:
        releases = json.loads(resp.read())
        for release in releases["assets"]:
            if not release["name"].endswith("cbor"):
                continue
            if release["name"].startswith(codename):
                durl = release["browser_download_url"]
                break

    if not durl:
        print(f"Could not find release with codename '{codename}', skipping")
        return 0

    version = ""
    target = ""
    with urlopen(durl) as resp:  # noqa: S310
        patch = cbor2.loads(resp.read())
        for content in patch.get("contents"):
            if content.get("source", "").startswith("UMU-Proton"):
                version = content["source"]
                target = content["target"]
                break

    # Verify the latest release matches the patch's target
    url = "https://api.github.com/repos/Open-Wine-Components/umu-proton/releases/latest"
    durl = ""
    is_target = False
    with urlopen(  # noqa: S310
        Request(url, headers=headers),  # noqa: S310
        context=ctx,
    ) as resp:
        releases = json.loads(resp.read())
        for release in releases["assets"]:
            if release["name"].startswith(target) and release["name"].endswith(
                ".tar.gz"
            ):
                is_target = True
                break

    # Case when the latest release doesn't match the patch target
    if not is_target:
        print(f"Latest release is not expected patch target '{target}', skipping")
        return 0

    durl = f"https://github.com/Open-Wine-Components/umu-proton/releases/download/{version}/{version}.tar.gz"
    with urlopen(durl) as resp:  # noqa: S310
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

    path = "/usr/local/bin"
    exe = shutil.which("umu-run", path=path)
    if exe is None:
        print(f"Could not find umu-run in '{path}', exiting")
        return 1

    return subprocess.run(
        (exe, "wineboot", "-u"),
        env={
            "PROTONPATH": "UMU-Latest",
            "GAMEID": "umu-0",
            "UMU_LOG": "1",
            "PATH": os.environ["PATH"],
        },
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
