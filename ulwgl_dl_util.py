from pathlib import Path
from os import environ
from requests import get
from tarfile import open as tar_open
from requests import Response
from typing import Dict, List, Tuple, Any, Union
from hashlib import sha512


def get_ulwgl_proton(env: Dict[str, str]) -> Union[Dict[str, str], None]:
    """Attempt to find Proton and downloads the latest if PROTONPATH is not set.

    Only fetches the latest if not first found in the Steam compat
    Cache is only referred to last
    """
    # TODO: Put this in the background
    files: List[Tuple[str, str]] = _fetch_releases()
    cache: Path = Path(Path().home().as_posix() + "/.cache/ULWGL")
    steam_compat: Path = Path(
        Path().home().as_posix() + "/.local/share/Steam/compatibilitytools.d"
    )

    cache.mkdir(exist_ok=True, parents=True)
    steam_compat.mkdir(exist_ok=True, parents=True)

    # Prioritize the Steam compat
    for proton in steam_compat.glob("GE-Proton*"):
        print(f"{proton.name} found in: {steam_compat.as_posix()}")
        environ["PROTONPATH"] = proton.as_posix()
        env["PROTONPATH"] = environ["PROTONPATH"]

        # Notify the user that they're not using the latest
        if len(files) == 2 and proton.name != files[1][0][: files[1][0].find(".")]:
            print(
                "GE-Proton is outdated and requires manual intervention.\nFor latest release, please download "
                + files[1][0]
            )

        return env

    # Check if the latest isn't already in the cache
    # Assumes the tarball is legitimate
    if (
        files and Path(Path().home().as_posix() + "/.cache/ULWGL").joinpath(files[1][0])
    ).is_file():
        proton: str = files[1][0]

        print(f"{proton} found in: {cache.as_posix()}")
        _extract_dir(
            Path(Path().home().as_posix() + "/.cache/ULWGL").joinpath(proton),
            steam_compat,
        )

        environ["PROTONPATH"] = steam_compat.joinpath(
            proton[: proton.find(".")]
        ).as_posix()
        env["PROTONPATH"] = environ["PROTONPATH"]

        return env

    # Download the latest if GE-Proton is not in Steam compat
    # If the digests mismatched, refer to the cache in the next block
    if files:
        try:
            print("Fetching latest release ...")
            _fetch_proton(env, steam_compat, cache, files)
            env["PROTONPATH"] = environ["PROTONPATH"]

            return env
        except ValueError as err:
            print(err)

    # Cache
    for proton in cache.glob("GE-Proton*.tar.gz"):
        print(f"{proton.name} found in: {cache.as_posix()}")

        # Extract it to Steam compat then set it as Proton
        _extract_dir(proton, steam_compat)

        environ["PROTONPATH"] = steam_compat.joinpath(
            proton.name[: proton.name.find(".")]
        ).as_posix()
        env["PROTONPATH"] = environ["PROTONPATH"]

        return env

    # No internet and cache/compat tool is empty, just return and raise an exception from the caller
    return env


def _fetch_releases() -> List[Tuple[str, str]]:
    """Fetch the latest releases from the Github API."""
    resp: Response = get(
        "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases"
    )
    # The file name and its URL as one element
    # Checksum will be the first element, GE-Proton second
    files: List[Tuple[str, str]] = []

    if not resp or not resp.status_code == 200:
        return files

    # Attempt to acquire the tarball and checksum from the JSON data
    releases: List[Dict[str, Any]] = resp.json()
    for release in releases:
        if "assets" in release:
            assets: List[Dict[str, Any]] = release["assets"]

            for asset in assets:
                if (
                    "name" in asset
                    and (
                        asset["name"].endswith("sum")
                        or (
                            asset["name"].endswith("tar.gz")
                            and asset["name"].startswith("GE-Proton")
                        )
                    )
                    and "browser_download_url" in asset
                ):
                    if asset["name"].endswith("sum"):
                        files.append((asset["name"], asset["browser_download_url"]))
                    else:
                        files.append((asset["name"], asset["browser_download_url"]))

                if len(files) == 2:
                    break
        break

    return files


def _fetch_proton(
    env: Dict[str, str], steam_compat: Path, cache: Path, files: List[Tuple[str, str]]
) -> Dict[str, str]:
    """Download the latest ULWGL-Proton and set it as PROTONPATH."""
    hash, hash_url = files[0]
    proton, proton_url = files[1]
    stored_digest: str = ""

    # TODO: Parallelize this
    print(f"Downloading {hash} ...")
    resp_hash: Response = get(hash_url)
    print(f"Downloading {proton} ...")
    resp: Response = get(proton_url)
    if (
        not resp_hash
        and resp_hash.status_code != 200
        and not resp
        and resp.status_code != 200
    ):
        err: str = "Failed.\nFalling back to cache directory ..."
        raise ValueError(err)

    print("Completed.")

    # Download the hash
    with Path(f"{cache.as_posix()}/{hash}").open(mode="wb") as file:
        file.write(resp_hash.content)
    stored_digest = Path(f"{cache.as_posix()}/{hash}").read_text().split(" ")[0]

    # If checksum fails, raise an error and fallback to the cache
    with Path(f"{cache.as_posix()}/{proton}").open(mode="wb") as file:
        file.write(resp.content)

        if sha512(resp.content).hexdigest() != stored_digest:
            err: str = "Digests mismatched.\nFalling back to the cache ..."
            raise ValueError(err)
        print(f"{proton}: SHA512 is OK")

    _extract_dir(Path(f"{cache.as_posix()}/{proton}"), steam_compat)
    environ["PROTONPATH"] = steam_compat.joinpath(proton[: proton.find(".")]).as_posix()
    env["PROTONPATH"] = environ["PROTONPATH"]

    return env


def _extract_dir(proton: Path, steam_compat: Path) -> None:
    """Extract from the cache and to another location."""
    with tar_open(proton.as_posix(), "r:gz") as tar:
        print(f"Extracting {proton} -> {steam_compat.as_posix()} ...")
        tar.extractall(path=steam_compat.as_posix())
