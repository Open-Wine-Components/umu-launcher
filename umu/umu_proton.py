import os
import sys
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha512
from http.client import HTTPException
from json import loads
from pathlib import Path
from re import split as resplit
from shutil import move, rmtree
from ssl import SSLContext, create_default_context
from tarfile import open as tar_open
from tempfile import TemporaryDirectory
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from filelock import FileLock

from umu.umu_consts import STEAM_COMPAT, UMU_CACHE, UMU_LOCAL
from umu.umu_log import log
from umu.umu_util import run_zenity

ssl_default_context: SSLContext = create_default_context()

try:
    from tarfile import tar_filter

    has_data_filter: bool = True
except ImportError:
    has_data_filter: bool = False


def get_umu_proton(
    env: dict[str, str], thread_pool: ThreadPoolExecutor
) -> dict[str, str]:
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
        assets = _fetch_releases()
    except URLError:
        log.debug("Network is unreachable")

    # TODO: Handle interrupts on the move/extract operations
    with (
        TemporaryDirectory() as tmp,
        TemporaryDirectory(dir=UMU_CACHE) as tmpcache,
    ):
        tmpdirs: tuple[Path, Path] = (Path(tmp), Path(tmpcache))
        if _get_latest(env, STEAM_COMPAT, tmpdirs, assets, thread_pool) is env:
            return env
        if _get_from_steamcompat(env, STEAM_COMPAT) is env:
            return env

    os.environ["PROTONPATH"] = ""

    return env


def _fetch_releases() -> tuple[tuple[str, str], tuple[str, str]] | tuple[()]:
    """Fetch the latest releases from the Github API."""
    digest_asset: tuple[str, str]
    proton_asset: tuple[str, str]
    releases: list[dict[str, Any]]
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

    with urlopen(  # noqa: S310
        Request(f"{url}{repo}", headers=headers),  # noqa: S310
        context=ssl_default_context,
    ) as resp:
        if resp.status != 200:
            return ()
        releases = loads(resp.read().decode("utf-8")).get("assets", [])

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
        if asset_count == 2:
            break

    if asset_count != 2:
        err: str = "Failed to acquire all assets from api.github.com"
        raise RuntimeError(err)

    return digest_asset, proton_asset


def _fetch_proton(
    env: dict[str, str],
    tmp: Path,
    assets: tuple[tuple[str, str], tuple[str, str]],
) -> dict[str, str]:
    """Download the latest UMU-Proton or GE-Proton."""
    proton_hash, proton_hash_url = assets[0]
    tarball, tar_url = assets[1]
    proton: str = tarball.removesuffix(".tar.gz")
    ret: int = 0  # Exit code from zenity
    digest: str = ""  # Digest of the Proton archive

    # Verify the scheme from Github for resources
    if not tar_url.startswith("https:") or not proton_hash_url.startswith("https:"):
        err: str = f"Scheme in URLs is not 'https:': {(tar_url, proton_hash_url)}"
        raise ValueError(err)

    # Digest file
    # Since the URLs are not hardcoded links, Ruff will flag the urlopen call
    # See https://github.com/astral-sh/ruff/issues/7918
    log.console(f"Downloading {proton_hash}...")
    with (urlopen(proton_hash_url, context=ssl_default_context) as resp,):  # noqa: S310
        if resp.status != 200:
            err: str = (
                f"Unable to download {proton_hash}\n"
                f"github.com returned the status: {resp.status}"
            )
            raise HTTPException(err)

        for line in resp.read().decode("utf-8").splitlines():
            if line.endswith(tarball):
                digest = line.split(" ")[0]

    # Proton
    # Create a popup with zenity when the env var is set
    if os.environ.get("UMU_ZENITY") == "1":
        curl: str = "curl"
        opts: list[str] = [
            "-LJO",
            "--silent",
            tar_url,
            "--output-dir",
            str(tmp),
        ]
        msg: str = f"Downloading {proton}..."
        ret = run_zenity(curl, opts, msg)

    if ret:
        tmp.joinpath(tarball).unlink(missing_ok=True)
        log.warning("zenity exited with the status code: %s", ret)
        log.console("Retrying from Python...")

    if not os.environ.get("UMU_ZENITY") or ret:
        log.console(f"Downloading {tarball}...")
        with (urlopen(tar_url, context=ssl_default_context) as resp,):  # noqa: S310
            hashsum = sha512()

            # Crash here because without Proton, the launcher will not work
            if resp.status != 200:
                err: str = (
                    f"Unable to download {tarball}\n"
                    f"github.com returned the status: {resp.status}"
                )
                raise HTTPException(err)

            with tmp.joinpath(tarball).open(mode="ab+", buffering=0) as file:
                chunk_size: int = 64 * 1024  # 64 KB
                buffer: bytearray = bytearray(chunk_size)
                view: memoryview = memoryview(buffer)
                while size := resp.readinto(buffer):
                    file.write(view[:size])
                    hashsum.update(view[:size])

            if hashsum.hexdigest() != digest:
                err: str = f"Digest mismatched: {tarball}"
                raise ValueError(err)

            log.console(f"{tarball}: SHA512 is OK")

    return env


def _extract_dir(file: Path) -> None:
    """Extract from a path to another location."""
    with tar_open(file, "r:gz") as tar:
        if has_data_filter:
            log.debug("Using filter for archive")
            tar.extraction_filter = tar_filter
        else:
            log.warning("Python: %s", sys.version)
            log.warning("Using no data filter for archive")
            log.warning("Archive will be extracted insecurely")
        log.console(f"Extracting {file.name}...")
        log.debug("Source: %s", str(file).removesuffix(".tar.gz"))
        tar.extractall(path=file.parent)  # noqa: S202


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
        log.console(f"{latest.name} found in '{steam_compat}'")
        log.console(f"Using {latest.name}")
        os.environ["PROTONPATH"] = str(latest)
        env["PROTONPATH"] = os.environ["PROTONPATH"]
    except ValueError:
        return None

    return env


def _get_latest(
    env: dict[str, str],
    steam_compat: Path,
    tmpdirs: tuple[Path, Path],
    assets: tuple[tuple[str, str], tuple[str, str]] | tuple[()],
    thread_pool: ThreadPoolExecutor,
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
    lock: FileLock

    if not assets:
        return None

    tarball = assets[1][0]
    proton = tarball.removesuffix(".tar.gz")
    version = (
        "GE-Proton" if os.environ.get("PROTONPATH") == "GE-Proton" else "UMU-Proton"
    )

    # Return if the latest Proton is already installed
    if steam_compat.joinpath(proton).is_dir():
        log.console(f"{version} is up to date")
        steam_compat.joinpath("UMU-Latest").unlink(missing_ok=True)
        steam_compat.joinpath("UMU-Latest").symlink_to(proton)
        os.environ["PROTONPATH"] = str(steam_compat.joinpath(proton))
        env["PROTONPATH"] = os.environ["PROTONPATH"]
        return env

    # Use the latest UMU/GE-Proton
    try:
        lock = FileLock(f"{UMU_LOCAL}/compatibilitytools.d.lock")
        log.debug("Acquiring file lock '%s'...", lock.lock_file)
        lock.acquire()

        # Once acquiring the lock check if Proton hasn't been installed
        if steam_compat.joinpath(proton).is_dir():
            raise FileExistsError

        # Download the archive to a temporary directory
        _fetch_proton(env, tmpdirs[0], assets)

        # Extract the archive then move the directory
        _install_proton(tarball, tmpdirs, steam_compat, thread_pool)
    except (
        ValueError,
        KeyboardInterrupt,
        HTTPException,
    ) as e:
        log.exception(e)
        return None
    except FileExistsError:
        pass
    finally:
        log.debug("Released file lock '%s'", lock.lock_file)
        lock.release()

    os.environ["PROTONPATH"] = str(steam_compat.joinpath(proton))
    env["PROTONPATH"] = os.environ["PROTONPATH"]
    log.debug("Removing: %s", tarball)
    log.console(f"Using {proton}")

    return env


def _update_proton(
    protons: list[Path],
    thread_pool: ThreadPoolExecutor,
) -> None:
    """Create a symbolic link and remove the previous UMU-Proton.

    The symbolic link will be used by clients to reference the PROTONPATH which
    can be used for tasks such as killing the running wineserver in the prefix.
    The link will be recreated each run.

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
    tmpdirs: tuple[Path, Path],
    steam_compat: Path,
    thread_pool: ThreadPoolExecutor,
) -> None:
    """Install a Proton directory to Steam's compatibilitytools.d.

    An installation is primarily composed of two steps: extract and move. A
    UMU-Proton or GE-Proton build will first be extracted to a secure temporary
    directory then moved to compatibilitytools.d, which is expected to be in
    $HOME. In the case of UMU-Proton, an installation will include a remove
    step, where old builds will be removed in parallel.
    """
    future: Future | None = None
    version: str = (
        "GE-Proton" if os.environ.get("PROTONPATH") == "GE-Proton" else "UMU-Proton"
    )
    proton: str = tarball.removesuffix(".tar.gz")
    archive_path: str = f"{tmpdirs[0]}/{tarball}"
    proton_path: str = f"{tmpdirs[1]}/{proton}"

    # TODO: Refactor when differential updates are implemented.
    # Remove all previous builds when the build is UMU-Proton
    if version == "UMU-Proton":
        protons: list[Path] = [
            file
            for file in steam_compat.glob("*")
            if file.name.startswith(("UMU-Proton", "ULWGL-Proton"))
        ]
        future = thread_pool.submit(_update_proton, protons, thread_pool)

    # Move downloaded file from tmpfs to cache to avoid high memory usage
    log.debug("Moving: %s -> %s", archive_path, tmpdirs[1])
    move(archive_path, tmpdirs[1])

    _extract_dir(tmpdirs[1] / tarball)

    # Move decompressed archive to compatibilitytools.d
    log.console(f"'{proton_path}' -> '{steam_compat}'")
    move(proton_path, steam_compat)

    steam_compat.joinpath("UMU-Latest").unlink(missing_ok=True)
    steam_compat.joinpath("UMU-Latest").symlink_to(proton)
    log.debug("Linking: UMU-Latest -> %s", proton)

    if future:
        future.result()
