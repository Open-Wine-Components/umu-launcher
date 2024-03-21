from tarfile import open as tar_open, TarInfo
from pathlib import Path
from os import environ
from typing import Dict, List, Tuple, Any, Union, Callable
from hashlib import sha512
from shutil import rmtree
from http.client import HTTPSConnection, HTTPResponse, HTTPException, HTTPConnection
from ssl import create_default_context
from json import loads as loads_json
from urllib.request import urlopen
from umu_plugins import enable_zenity
from socket import gaierror
from umu_log import log
from umu_consts import STEAM_COMPAT, UMU_CACHE

try:
    from tarfile import tar_filter
except ImportError:
    tar_filter: Callable[[str, str], TarInfo] = None


def get_umu_proton(env: Dict[str, str]) -> Union[Dict[str, str]]:
    """Attempt to find existing Proton from the system.

    Downloads the latest if not first found in:
    ~/.local/share/Steam/compatibilitytools.d

    The cache directory ~/.cache/umu is referenced for the latest then as
    fallback
    """
    files: List[Tuple[str, str]] = []

    try:
        files = _fetch_releases()
    except gaierror:
        pass  # User is offline

    UMU_CACHE.mkdir(exist_ok=True, parents=True)
    STEAM_COMPAT.mkdir(exist_ok=True, parents=True)

    # Prioritize the Steam compat
    if _get_from_steamcompat(env, STEAM_COMPAT, UMU_CACHE):
        return env

    # Use the latest Proton in the cache if it exists
    if _get_from_cache(env, STEAM_COMPAT, UMU_CACHE, files, True):
        return env

    # Download the latest if Proton is not in Steam compat
    # If the digests mismatched, refer to the cache in the next block
    if _get_latest(env, STEAM_COMPAT, UMU_CACHE, files):
        return env

    # Refer to an old version previously downloaded
    # Reached on digest mismatch, user interrupt or download failure/no internet
    if _get_from_cache(env, STEAM_COMPAT, UMU_CACHE, files, False):
        return env

    # No internet and cache/compat tool is empty, just return and raise an
    # exception from the caller
    return env


def _fetch_releases() -> List[Tuple[str, str]]:
    """Fetch the latest releases from the Github API."""
    files: List[Tuple[str, str]] = []
    resp: HTTPResponse = None
    conn: HTTPConnection = HTTPSConnection(
        "api.github.com", timeout=30, context=create_default_context()
    )

    conn.request(
        "GET",
        "/repos/Open-Wine-Components/umu-proton/releases",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "",
        },
    )

    resp = conn.getresponse()

    if resp.status != 200:
        return files

    # Attempt to acquire the tarball and checksum from the JSON data
    releases: List[Dict[str, Any]] = loads_json(resp.read().decode("utf-8"))
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
                            and asset["name"].startswith(("umu-proton", "ULWGL-Proton"))
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
    conn.close()
    if len(files) != 2:
        err: str = "Failed to get complete information for Proton release"
        raise RuntimeError(err)

    return files


def _fetch_proton(
    env: Dict[str, str], steam_compat: Path, cache: Path, files: List[Tuple[str, str]]
) -> Dict[str, str]:
    """Download the latest umu-proton and set it as PROTONPATH."""
    hash, hash_url = files[0]
    proton, proton_url = files[1]
    proton_dir: str = proton[: proton.find(".tar.gz")]  # Proton dir

    log.console(f"Downloading {hash} ...")

    # Verify the scheme from Github for resources
    if not proton_url.startswith("https:") or not hash_url.startswith("https:"):
        urls = [proton_url, hash_url]
        err: str = f"Scheme in URLs is not 'https:': {urls}"
        raise ValueError(err)

    # Digest file
    # Ruff currently cannot get this right
    # See https://github.com/astral-sh/ruff/issues/7918
    with urlopen(hash_url, timeout=30, context=create_default_context()) as resp:  # noqa: S310
        if resp.status != 200:
            err: str = (
                f"Unable to download {hash}\n"
                f"github.com returned the status: {resp.status}"
            )
            raise HTTPException(err)
        with cache.joinpath(hash).open(mode="wb") as file:
            file.write(resp.read())

    # Proton
    # Check for Zenity otherwise print
    try:
        bin: str = "curl"
        opts: List[str] = [
            "-LJO",
            "--silent",
            proton_url,
            "--output-dir",
            cache.as_posix(),
        ]

        msg: str = f"Downloading {proton_dir} ..."
        enable_zenity(bin, opts, msg)
    except TimeoutError:
        err: str = f"Unable to download {proton}\ngithub.com request timed out"
        raise TimeoutError(err)
    except FileNotFoundError:
        log.console(f"Downloading {proton} ...")

        with urlopen(proton_url, timeout=180, context=create_default_context()) as resp:  # noqa: S310
            # Without Proton, the launcher will not work
            # Continue by referring to cache
            if resp.status != 200:
                err: str = (
                    f"Unable to download {proton}\n"
                    f"github.com returned the status: {resp.status}"
                )
                raise HTTPException(err)
            with cache.joinpath(proton).open(mode="wb") as file:
                file.write(resp.read())

    log.console("Completed.")

    with cache.joinpath(proton).open(mode="rb") as file:
        if (
            sha512(file.read()).hexdigest()
            != cache.joinpath(hash).read_text().split(" ")[0]
        ):
            err: str = "Digests mismatched.\nFalling back to cache ..."
            raise ValueError(err)
        log.console(f"{proton}: SHA512 is OK")

    _extract_dir(cache.joinpath(proton), steam_compat)
    environ["PROTONPATH"] = steam_compat.joinpath(proton_dir).as_posix()
    env["PROTONPATH"] = environ["PROTONPATH"]

    return env


def _extract_dir(proton: Path, steam_compat: Path) -> None:
    """Extract from the cache to another location."""
    with tar_open(proton.as_posix(), "r:gz") as tar:
        if tar_filter:
            log.debug("Using filter for archive")
            tar.extraction_filter = tar_filter
        else:
            log.debug("Using no filter for archive")
            log.warning("Archive will be extracted insecurely")

        log.console(f"Extracting {proton} -> {steam_compat} ...")
        tar.extractall(path=steam_compat.as_posix())  # noqa: S202
        log.console("Completed.")


def _cleanup(tarball: str, proton: str, cache: Path, steam_compat: Path) -> None:
    """Remove files that may have been left in an incomplete state to avoid corruption.

    We want to do this when a download for a new release is interrupted
    """
    log.console("Keyboard Interrupt.\nCleaning ...")

    if cache.joinpath(tarball).is_file():
        log.console(f"Purging {tarball} in {cache} ...")
        cache.joinpath(tarball).unlink()
    if steam_compat.joinpath(proton).is_dir():
        log.console(f"Purging {proton} in {steam_compat} ...")
        rmtree(steam_compat.joinpath(proton).as_posix())


def _get_from_steamcompat(
    env: Dict[str, str], steam_compat: Path, cache: Path, files: List[Tuple[str, str]]
) -> Union[Dict[str, str], None]:
    """Refer to Steam compat folder for any existing Proton directories."""
    proton_dir: str = ""  # Latest Proton

    if len(files) == 2:
        proton_dir: str = files[1][0][: files[1][0].find(".tar.gz")]

    for proton in steam_compat.glob("umu-Proton*"):
        log.console(f"{proton.name} found in: {steam_compat}")
        log.console(f"Using {proton.name}")

        environ["PROTONPATH"] = proton.as_posix()
        env["PROTONPATH"] = environ["PROTONPATH"]

        # Notify the user that they're not using the latest
        if proton_dir and proton.name != proton_dir:
            link: str = files[1][1]
            log.console(
                "umu-Proton is outdated.\n"
                f"For latest release, please download {link}"
            )

        return env

    return None


def _get_from_cache(
    env: Dict[str, str],
    steam_compat: Path,
    cache: Path,
    files: List[Tuple[str, str]],
    use_latest: bool = True,
) -> Union[Dict[str, str], None]:
    """Refer to umu cache directory.

    Use the latest in the cache when present. When download fails, use an old version
    Older Proton versions are only referred to when: digests mismatch, user
    interrupt, or download failure/no internet
    """
    path: Path = None
    name: str = ""

    for tarball in cache.glob("umu-Proton*.tar.gz"):
        # Online
        if files and tarball == cache.joinpath(files[1][0]) and use_latest:
            path = tarball
            name = tarball.name
            break
        # Offline, download interrupt, digest mismatch
        if not files or not use_latest:
            path = tarball
            name = tarball.name
            break

    if path:
        proton_dir: str = name[: name.find(".tar.gz")]  # Proton dir

        log.console(f"{name} found in: {path}")
        try:
            _extract_dir(path, steam_compat)

            log.console(f"Using {proton_dir}")
            environ["PROTONPATH"] = steam_compat.joinpath(proton_dir).as_posix()
            env["PROTONPATH"] = environ["PROTONPATH"]

            return env
        except KeyboardInterrupt:
            if steam_compat.joinpath(proton_dir).is_dir():
                log.console(f"Purging {proton_dir} in {steam_compat} ...")
                rmtree(steam_compat.joinpath(proton_dir).as_posix())
            raise

    return None


def _get_latest(
    env: Dict[str, str], steam_compat: Path, cache: Path, files: List[Tuple[str, str]]
) -> Union[Dict[str, str], None]:
    """Download the latest Proton for new installs -- empty cache and Steam compat.

    When the digests mismatched or when interrupted, refer to cache for an old version
    """
    if files:
        log.console("Fetching latest release ...")

        try:
            tarball: str = files[1][0]
            proton_dir: str = tarball[: tarball.find(".tar.gz")]  # Proton dir

            _fetch_proton(env, steam_compat, cache, files)

            log.console(f"Using {proton_dir}")
            env["PROTONPATH"] = environ["PROTONPATH"]
        except ValueError:
            log.exception("Exception")
            tarball: str = files[1][0]

            # Digest mismatched
            # Refer to the cache for old version next
            # Since we do not want the user to use a suspect file, delete it
            cache.joinpath(tarball).unlink(missing_ok=True)
            return None
        except KeyboardInterrupt:
            tarball: str = files[1][0]
            proton_dir: str = tarball[: tarball.find(".tar.gz")]  # Proton dir

            # Exit cleanly
            # Clean up extracted data and cache to prevent corruption/errors
            # Refer to the cache for old version next
            _cleanup(tarball, proton_dir, cache, steam_compat)
            return None
        except HTTPException:
            # Download failed
            return None

    return env
