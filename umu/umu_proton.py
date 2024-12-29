import os
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha512
from http import HTTPStatus
from pathlib import Path
from re import split as resplit
from shutil import move, rmtree
from tempfile import TemporaryDirectory
from typing import Any

from urllib3.exceptions import HTTPError
from urllib3.exceptions import TimeoutError as TimeoutErrorUrllib3
from urllib3.poolmanager import PoolManager
from urllib3.response import BaseHTTPResponse

from umu.umu_consts import STEAM_COMPAT, UMU_CACHE, UMU_LOCAL, HTTPMethod
from umu.umu_log import log
from umu.umu_util import (
    extract_tarfile,
    file_digest,
    run_zenity,
    unix_flock,
    write_file_chunks,
)

SessionPools = tuple[ThreadPoolExecutor, PoolManager]

# Unique subdir in /tmp
CacheTmpfs = Path

# Unique subdir in $XDG_CACHE_HOME/umu
CacheSubdir = Path

SessionCaches = tuple[CacheTmpfs, CacheSubdir]


def get_umu_proton(env: dict[str, str], session_pools: SessionPools) -> dict[str, str]:
    """Attempt to use the latest Proton when configured.

    When $PROTONPATH is not set or $PROTONPATH is 'GE-Proton', the launcher
    will make a request to Github for the latest UMU-Proton or GE-Proton build
    and attempt to use it if not already installed in '$HOME/.local/share/Steam
    /compatibilitytools.d'.

    Protons installed in system paths will not be searched. When the user's
    network is unreachable, the launcher will fallback to using the latest
    version of UMU-Proton or GE-Proton installed.
    """
    # Subset of Github release assets from the Github API (ver. 2022-11-28)
    # First element is the digest asset, second is the Proton asset. Each asset
    # will contain the asset's name and the URL that hosts it.
    assets: tuple[tuple[str, str], tuple[str, str]] | tuple[()] = ()
    STEAM_COMPAT.mkdir(exist_ok=True, parents=True)
    UMU_CACHE.mkdir(parents=True, exist_ok=True)

    try:
        log.debug("Sending request to 'api.github.com'...")
        assets = _fetch_releases(session_pools)
    except HTTPError:
        log.debug("Network is unreachable")

    with (
        TemporaryDirectory() as tmp,
        TemporaryDirectory(dir=UMU_CACHE) as tmpcache,
    ):
        tmpdirs: SessionCaches = (Path(tmp), Path(tmpcache))
        if _get_latest(env, STEAM_COMPAT, tmpdirs, assets, session_pools) is env:
            return env
        if _get_from_steamcompat(env, STEAM_COMPAT) is env:
            return env

    os.environ["PROTONPATH"] = ""

    return env


def _fetch_releases(
    session_pools: SessionPools,
) -> tuple[tuple[str, str], tuple[str, str]] | tuple[()]:
    """Fetch the latest releases from the Github API."""
    resp: BaseHTTPResponse
    digest_asset: tuple[str, str]
    proton_asset: tuple[str, str]
    releases: list[dict[str, Any]]
    _, http_pool = session_pools
    asset_count: int = 0
    url: str = "https://api.github.com"
    repo: str = "/repos/Open-Wine-Components/umu-proton/releases/latest"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "",
    }

    if os.environ.get("PROTONPATH") == "GE-Proton":
        repo = "/repos/GloriousEggroll/proton-ge-custom/releases/latest"

    resp = http_pool.request(HTTPMethod.GET.value, f"{url}{repo}", headers=headers)
    if resp.status != HTTPStatus.OK:
        return ()

    releases = resp.json().get("assets", [])
    for release in releases:
        if release["name"].endswith("sum"):
            digest_asset = (
                release["name"],
                release["browser_download_url"],
            )
            asset_count += 1
            continue
        if release["name"].endswith("tar.gz") and release["name"].startswith(
            ("UMU-Proton", "GE-Proton")
        ):
            proton_asset = (
                release["name"],
                release["browser_download_url"],
            )
            asset_count += 1
            continue
        if asset_count == 2:  # noqa: PLR2004
            break

    if asset_count != 2:  # noqa: PLR2004
        log.warning("Failed to acquire release assets from '%s'", url)
        log.debug("'%' returned: %s", url, releases)
        return ()

    return digest_asset, proton_asset


def _fetch_proton(
    env: dict[str, str],
    session_caches: SessionCaches,
    assets: tuple[tuple[str, str], tuple[str, str]],
    session_pools: SessionPools,
) -> dict[str, str]:
    """Download the latest UMU-Proton or GE-Proton."""
    resp: BaseHTTPResponse
    tmpfs, cache = session_caches
    _, http_pool = session_pools
    proton_hash, proton_hash_url = assets[0]
    tarball, tar_url = assets[1]
    proton: str = tarball.removesuffix(".tar.gz")
    ret: int = 0  # Exit code from zenity
    digest: str = ""  # Digest of the Proton archive
    hashsum = sha512()

    # Verify the scheme from Github for resources
    if not tar_url.startswith("https:") or not proton_hash_url.startswith("https:"):
        err: str = f"Scheme in URLs is not 'https:': {(tar_url, proton_hash_url)}"
        raise ValueError(err)

    # Digest file
    # Since the URLs are not hardcoded links, Ruff will flag the urlopen call
    # See https://github.com/astral-sh/ruff/issues/7918
    log.info("Downloading %s...", proton_hash)

    resp = http_pool.request(
        HTTPMethod.GET.value, proton_hash_url, preload_content=False
    )
    if resp.status != HTTPStatus.OK:
        err: str = (
            f"Unable to download {proton_hash}\n"
            f"{resp.getheader('Host')} returned the status: {resp.status}"
        )
        raise HTTPError(err)

    # Parse data for the archive digest
    target: bytes = tarball.encode()
    while line := resp.readline():
        if line.rstrip().endswith(target):
            digest = line.split(b" ")[0].rstrip().decode()
            break

    resp.release_conn()

    # Proton
    # Create a popup with zenity when the env var is set
    if os.environ.get("UMU_ZENITY") == "1":
        curl: str = "curl"
        opts: list[str] = [
            "-LJO",
            "--silent",
            tar_url,
            "--output-dir",
            str(tmpfs),
        ]
        msg: str = f"Downloading {proton}..."
        ret = run_zenity(curl, opts, msg)

    if ret:
        tmpfs.joinpath(tarball).unlink(missing_ok=True)
        log.warning("zenity exited with the status code: %s", ret)
        log.info("Retrying from Python...")

    if not os.environ.get("UMU_ZENITY") or ret:
        parts: Path = tmpfs.joinpath(f"{tarball}.parts")
        cached_parts: Path = UMU_CACHE.joinpath(parts.name)
        headers: dict[str, str] | None = None

        # Resume from our cached file, if we were interrupted previously
        if cached_parts.is_file():
            log.info("Found '%s' in cache, resuming...", cached_parts.name)
            headers = {"Range": f"bytes={cached_parts.stat().st_size}-"}
            parts = cached_parts
            # Rebuild our hashed progress
            with parts.open("rb") as fp:
                hashsum = file_digest(fp, hashsum.name)
        else:
            log.info("Downloading %s...", tarball)

        resp = http_pool.request(
            HTTPMethod.GET.value,
            tar_url,
            preload_content=False,
            headers=headers,
        )

        # Bail out for unexpected status codes
        if resp.status not in {
            HTTPStatus.OK,
            HTTPStatus.PARTIAL_CONTENT,
            HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE,
        }:
            err: str = f"{resp.getheader('Host')} returned the status: {resp.status}"
            raise HTTPError(err)

        # Only write our file if we're resuming or downloading first time
        if resp.status != HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE:
            try:
                log.debug("Writing: %s", parts)
                hashsum = write_file_chunks(parts, resp, hashsum)
            except TimeoutErrorUrllib3:
                log.error("Aborting Proton install due to network error")
                log.info("Moving '%s' to cache for future resumption", parts.name)
                log.debug("Moving: %s -> %s", parts, cache.parent)
                move(parts, cache.parent)
                raise

        # Release conn to the pool
        resp.release_conn()

        log.debug("Digest: %s", digest)
        if hashsum.hexdigest() != digest:
            parts.unlink(missing_ok=True)
            err: str = (
                f"Digest mismatched: {tarball}\n"
                "Possible reason: cached file corrupted or failed to acquire upstream digest\n"
                f"Link: {tar_url}"
            )
            raise ValueError(err)

        log.info("%s: SHA512 is OK", tarball)

    return env


def _get_from_steamcompat(
    env: dict[str, str], steam_compat: Path
) -> dict[str, str] | None:
    """Refer to Steam's compatibilitytools.d folder for any existing Protons.

    When an error occurs in the process of using the latest Proton build either
    from a digest mismatch, request failure or unreachable network, the latest
    existing Proton build of that same version will be used
    """
    version: str = (
        "GE-Proton" if os.environ.get("PROTONPATH") == "GE-Proton" else "UMU-Proton"
    )

    try:
        latest: Path = max(
            (
                proton
                for proton in steam_compat.glob("*")
                if proton.name.startswith(version)
            ),
            key=lambda proton: [
                int(text) if text.isdigit() else text.lower()
                for text in resplit(r"(\d+)", proton.name)
            ],
        )
        log.info("%s found in '%s'", latest.name, steam_compat)
        log.info("Using %s", latest.name)
        os.environ["PROTONPATH"] = str(latest)
        env["PROTONPATH"] = os.environ["PROTONPATH"]
    except ValueError:
        return None

    return env


def _get_latest(
    env: dict[str, str],
    steam_compat: Path,
    session_caches: SessionCaches,
    assets: tuple[tuple[str, str], tuple[str, str]] | tuple[()],
    session_pools: SessionPools,
) -> dict[str, str] | None:
    """Download the latest Proton for new installs.

    Either GE-Proton or UMU-Proton can be downloaded. When download the latest
    UMU-Proton build, previous stable versions of that build will be deleted
    automatically. Previous GE-Proton builds will remain on the system because
    regressions are likely to occur in bleeding-edge based builds.

    When the digests mismatched or when interrupted, an old build will in
    $HOME/.local/share/Steam/compatibilitytool.d will be used.
    """
    # Name of the Proton archive (e.g., GE-Proton9-7.tar.gz)
    tarball: str
    # Name of the Proton directory (e.g., GE-Proton9-7)
    proton: str
    # Name of the Proton version, which is either UMU-Proton or GE-Proton
    version: str
    lockfile: str = f"{UMU_LOCAL}/compatibilitytools.d.lock"

    if not assets:
        return None

    tarball = assets[1][0]
    proton = tarball.removesuffix(".tar.gz")
    version = (
        "GE-Proton" if os.environ.get("PROTONPATH") == "GE-Proton" else "UMU-Proton"
    )

    # Return if the latest Proton is already installed
    if steam_compat.joinpath(proton).is_dir():
        log.info("%s is up to date", version)
        steam_compat.joinpath("UMU-Latest").unlink(missing_ok=True)
        steam_compat.joinpath("UMU-Latest").symlink_to(proton)
        os.environ["PROTONPATH"] = str(steam_compat.joinpath(proton))
        env["PROTONPATH"] = os.environ["PROTONPATH"]
        return env

    # Use the latest UMU/GE-Proton
    try:
        log.debug("Acquiring file lock '%s'...", lockfile)
        with unix_flock(lockfile):
            # Once acquiring the lock check if Proton hasn't been installed
            if steam_compat.joinpath(proton).is_dir():
                raise FileExistsError

            # Download the archive to a temporary directory
            _fetch_proton(env, session_caches, assets, session_pools)

            # Extract the archive then move the directory
            _install_proton(
                tarball, session_caches, steam_compat, session_pools
            )
    except (
        ValueError,
        KeyboardInterrupt,
        HTTPError,
    ) as e:
        log.exception(e)
        return None
    except FileExistsError:
        # Proton was installed by another proc, continue
        pass

    log.debug("Released file lock '%s'", lockfile)
    os.environ["PROTONPATH"] = str(steam_compat.joinpath(proton))
    env["PROTONPATH"] = os.environ["PROTONPATH"]
    log.debug("Removing: %s", tarball)
    log.info("Using %s", proton)

    return env


def _update_proton(
    protons: list[Path],
    thread_pool: ThreadPoolExecutor,
) -> None:
    """Remove previous stable UMU-Proton builds.

    Assumes that the directories that are named ULWGL/UMU-Proton are ours and
    will be removed, so users should not be storing important files there.
    """
    futures: list[Future] = []
    log.debug("Updating UMU-Proton")
    log.debug("Previous builds: %s", protons)

    if not protons:
        return

    for stable in protons:
        if stable.is_dir():
            log.debug("Previous stable build found")
            log.debug("Removing: %s", stable)
            futures.append(thread_pool.submit(rmtree, str(stable)))

    for future in futures:
        future.result()


def _install_proton(
    tarball: str,
    session_caches: SessionCaches,
    steam_compat: Path,
    session_pools: SessionPools,
) -> None:
    """Install a Proton directory to Steam's compatibilitytools.d.

    An installation is primarily composed of two steps: extract and move. A
    UMU-Proton or GE-Proton build will first be extracted to a secure temporary
    directory then moved to compatibilitytools.d, which is expected to be in
    $HOME. In the case of UMU-Proton, an installation will include a remove
    step, where old builds will be removed in parallel.
    """
    future: Future | None = None
    tmpfs, cache = session_caches
    thread_pool, _ = session_pools
    parts: str = f"{tarball}.parts"
    cached_parts: Path = cache.parent.joinpath(f"{tarball}.parts")
    version: str = (
        "GE-Proton" if os.environ.get("PROTONPATH") == "GE-Proton" else "UMU-Proton"
    )

    # TODO: Refactor when differential updates are implemented.
    # Remove all previous builds when the build is UMU-Proton
    if version == "UMU-Proton":
        protons: list[Path] = [
            file
            for file in steam_compat.glob("*")
            if file.name.startswith(("UMU-Proton", "ULWGL-Proton"))
        ]
        future = thread_pool.submit(_update_proton, protons, thread_pool)

    # Move our file and extract within our cache
    if cached_parts.is_file():
        # In this case, arc is already in cache and checksum'd
        log.debug("Moving: %s -> %s", cached_parts, cached_parts.with_suffix(""))
        move(cached_parts, cached_parts.with_suffix(""))
        # Move the archive to our unique subdir
        log.debug("Moving: %s -> %s", cached_parts.with_suffix(""), cache)
        move(cached_parts.with_suffix(""), cache)
        log.info("Extracting %s...", tarball)
        # Extract within the subdir
        extract_tarfile(cache.joinpath(tarball), cache.joinpath(tarball).parent)
    else:
        # The archive is in tmpfs. Remove the parts extension
        move(tmpfs.joinpath(parts), tmpfs.joinpath(tarball))
        move(tmpfs.joinpath(tarball), cache)
        log.info("Extracting %s...", tarball)
        extract_tarfile(cache.joinpath(tarball), cache.joinpath(tarball).parent)

    # Move decompressed archive to compatibilitytools.d
    log.info(
        "%s -> %s",
        cache.joinpath(tarball.removesuffix(".tar.gz")),
        steam_compat,
    )
    move(cache.joinpath(tarball.removesuffix(".tar.gz")), steam_compat)

    steam_compat.joinpath("UMU-Latest").unlink(missing_ok=True)
    steam_compat.joinpath("UMU-Latest").symlink_to(tarball.removesuffix(".tar.gz"))
    log.debug("Linking: UMU-Latest -> %s", tarball.removesuffix(".tar.gz"))

    if future:
        future.result()
