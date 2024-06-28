from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha512
from http.client import HTTPException
from json import loads
from os import environ
from pathlib import Path
from shutil import rmtree
from ssl import SSLContext, create_default_context
from sys import version
from tarfile import TarInfo
from tarfile import open as tar_open
from tempfile import mkdtemp
from urllib.request import Request, URLError, urlopen

from umu_consts import STEAM_COMPAT
from umu_log import log
from umu_util import run_zenity

SSL_DEFAULT_CONTEXT: SSLContext = create_default_context()

try:
    from tarfile import tar_filter
except ImportError:
    tar_filter: Callable[[str, str], TarInfo] = None


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
    files: list[tuple[str, str]] = []
    tmp: Path = Path(mkdtemp())
    STEAM_COMPAT.mkdir(exist_ok=True, parents=True)

    try:
        log.debug("Sending request to api.github.com")
        files = _fetch_releases()
    except URLError:
        log.debug("Network is unreachable")

    # Download the latest Proton
    if _get_latest(env, STEAM_COMPAT, tmp, files, thread_pool) is env:
        return env

    # When offline or an error occurs, use the first Proton in
    # compatibilitytools.d
    if _get_from_steamcompat(env, STEAM_COMPAT) is env:
        return env

    # No internet and compat tool is empty, just return and raise an
    # exception from the caller
    environ["PROTONPATH"] = ""

    return env


def _fetch_releases() -> list[tuple[str, str]]:
    """Fetch the latest releases from the Github API."""
    files: list[tuple[str, str]] = []
    url: str = "https://api.github.com"
    repo: str = "/repos/Open-Wine-Components/umu-proton/releases"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "",
    }

    if environ.get("PROTONPATH") == "GE-Proton":
        repo = "/repos/GloriousEggroll/proton-ge-custom/releases"

    with urlopen(  # noqa: S310
        Request(f"{url}{repo}", headers=headers),  # noqa: S310
        context=SSL_DEFAULT_CONTEXT,
    ) as resp:
        if resp.status != 200:
            return files

        for release in loads(resp.read().decode("utf-8")):
            if not release.get("assets"):
                continue
            for asset in release.get("assets"):
                if (
                    asset.get("name")
                    and (
                        asset.get("name").endswith("sum")
                        or (
                            asset.get("name").endswith("tar.gz")
                            and asset.get("name").startswith(
                                ("UMU-Proton", "GE-Proton")
                            )
                        )
                    )
                    and asset.get("browser_download_url")
                ):
                    if asset["name"].endswith("sum"):
                        files.append(
                            (asset["name"], asset["browser_download_url"])
                        )
                    else:
                        files.append(
                            (asset["name"], asset["browser_download_url"])
                        )
                if len(files) == 2:
                    break
            break

    if len(files) != 2:
        err: str = (
            "Failed to get complete information for Proton at api.github.com"
        )
        raise RuntimeError(err)

    return files


def _fetch_proton(
    env: dict[str, str], tmp: Path, files: list[tuple[str, str]]
) -> dict[str, str]:
    hash, hash_url = files[0]
    proton, proton_url = files[1]
    proton_dir: str = proton[: proton.find(".tar.gz")]  # Proton dir
    """Download the latest UMU-Proton or GE-Proton."""
    ret: int = 0  # Exit code from zenity
    digest: str = ""  # Digest of the Proton archive

    # Verify the scheme from Github for resources
    if not proton_url.startswith("https:") or not hash_url.startswith(
        "https:"
    ):
        urls = [proton_url, hash_url]
        err: str = f"Scheme in URLs is not 'https:': {urls}"
        raise ValueError(err)

    # Digest file
    # Ruff currently cannot get this right
    # See https://github.com/astral-sh/ruff/issues/7918
    log.console(f"Downloading {hash}...")
    with (
        urlopen(hash_url, context=SSL_DEFAULT_CONTEXT) as resp,  # noqa: S310
    ):
        if resp.status != 200:
            err: str = (
                f"Unable to download {hash}\n"
                f"github.com returned the status: {resp.status}"
            )
            raise HTTPException(err)

        for line in resp.read().decode("utf-8").splitlines():
            if line.endswith(proton):
                digest = line.split(" ")[0]

    # Proton
    # Create a popup with zenity when the env var is set
    if environ.get("UMU_ZENITY") == "1":
        bin: str = "curl"
        opts: list[str] = [
            "-LJO",
            "--silent",
            proton_url,
            "--output-dir",
            str(tmp),
        ]
        msg: str = f"Downloading {proton_dir}..."
        ret = run_zenity(bin, opts, msg)

    if ret:
        tmp.joinpath(proton).unlink(missing_ok=True)
        log.warning("zenity exited with the status code: %s", ret)
        log.console("Retrying from Python...")

    if not environ.get("UMU_ZENITY") or ret:
        log.console(f"Downloading {proton}...")
        with (
            urlopen(  # noqa: S310
                proton_url, context=SSL_DEFAULT_CONTEXT
            ) as resp,
        ):
            hash = sha512()

            # Crash here because without Proton, the launcher will not work
            if resp.status != 200:
                err: str = (
                    f"Unable to download {proton}\n"
                    f"github.com returned the status: {resp.status}"
                )
                raise HTTPException(err)

            with tmp.joinpath(proton).open(mode="ab+", buffering=0) as file:
                chunk_size: int = 64 * 1024  # 64 KB
                buffer: bytearray = bytearray(chunk_size)
                view: memoryview = memoryview(buffer)
                while size := resp.readinto(buffer):
                    file.write(view[:size])
                    hash.update(view[:size])

            if hash.hexdigest() != digest:
                err: str = f"Digest mismatched: {proton}"
                raise ValueError(err)

            log.console(f"{proton}: SHA512 is OK")

    return env


def _extract_dir(file: Path, steam_compat: Path) -> None:
    """Extract from a path to another location."""
    with tar_open(file, "r:gz") as tar:
        if tar_filter:
            log.debug("Using filter for archive")
            tar.extraction_filter = tar_filter
        else:
            log.warning("Python: %s", version)
            log.warning("Using no data filter for archive")
            log.warning("Archive will be extracted insecurely")

        log.console(f"Extracting '{file}' -> '{steam_compat}'...")
        # TODO: Rather than extracting all of the contents, we should prefer
        # the difference (e.g., rsync)
        tar.extractall(path=steam_compat)  # noqa: S202


def _cleanup(tarball: str, proton: str, tmp: Path, steam_compat: Path) -> None:
    """Remove files that may have been left in an incomplete state.

    We want to do this when a download for a new release is interrupted to
    avoid corruption.
    """
    log.console("Keyboard Interrupt.\nCleaning...")

    if tmp.joinpath(tarball).is_file():
        log.console(f"Purging '{tarball}' in '{tmp}'...")
        tmp.joinpath(tarball).unlink()
    if steam_compat.joinpath(proton).is_dir():
        log.console(f"Purging '{proton}' in '{steam_compat}'...")
        rmtree(str(steam_compat.joinpath(proton)))


def _get_from_steamcompat(
    env: dict[str, str], steam_compat: Path
) -> dict[str, str] | None:
    """Refer to Steam's compatibilitytools.d folder for any existing Protons.

    When an error occurs in the process of using the latest Proton build either
    from a digest mismatch, request failure or unreachable network, the latest
    existing Proton build of that same version will be used
    """
    version: str = (
        "GE-Proton"
        if environ.get("PROTONPATH") == "GE-Proton"
        else "UMU-Proton"
    )

    try:
        latest: Path = max(
            proton
            for proton in steam_compat.glob("*")
            if proton.name.startswith(version)
        )
        log.console(f"{latest.name} found in: '{steam_compat}'")
        log.console(f"Using {latest.name}")
        environ["PROTONPATH"] = str(latest)
        env["PROTONPATH"] = environ["PROTONPATH"]
    except ValueError:
        return None

    return env


def _get_latest(
    env: dict[str, str],
    steam_compat: Path,
    tmp: Path,
    files: list[tuple[str, str]],
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
    tarball: str = ""
    # Name of the Proton directory (e.g., GE-Proton9-7)
    proton: str = ""
    # Name of the Proton version, which is either UMU-Proton or GE-Proton
    version: str = ""

    if not files:
        return None

    tarball = files[1][0]
    proton = tarball[: tarball.find(".tar.gz")]
    version = (
        "GE-Proton"
        if environ.get("PROTONPATH") == "GE-Proton"
        else "UMU-Proton"
    )

    # Return if the latest Proton is already installed
    if steam_compat.joinpath(proton).is_dir():
        log.console(f"{version} is up to date")
        steam_compat.joinpath("UMU-Latest").unlink(missing_ok=True)
        steam_compat.joinpath("UMU-Latest").symlink_to(proton)
        environ["PROTONPATH"] = str(steam_compat.joinpath(proton))
        env["PROTONPATH"] = environ["PROTONPATH"]
        return env

    # Use the latest UMU/GE-Proton
    try:
        _fetch_proton(env, tmp, files)
        if version == "UMU-Proton":
            protons: list[Path] = [
                file
                for file in steam_compat.glob("*")
                if file.name.startswith(("UMU-Proton", "ULWGL-Proton"))
            ]
            log.debug("Updating UMU-Proton")
            future: Future = thread_pool.submit(
                _update_proton, proton, steam_compat, protons, thread_pool
            )
            _extract_dir(tmp.joinpath(tarball), steam_compat)
            future.result()
        else:
            _extract_dir(tmp.joinpath(tarball), steam_compat)
        environ["PROTONPATH"] = str(steam_compat.joinpath(proton))
        env["PROTONPATH"] = environ["PROTONPATH"]
        log.debug("Removing: %s", tarball)
        thread_pool.submit(tmp.joinpath(tarball).unlink, True)
        log.console(f"Using {version} ({proton})")
    except ValueError as e:  # Digest mismatched
        log.exception(e)
        # Since we do not want the user to use a suspect file, delete it
        tmp.joinpath(tarball).unlink(missing_ok=True)
        return None
    except KeyboardInterrupt:  # ctrl+c or signal sent from parent proc
        # Clean up extracted data in compatibilitytools.d and temporary dir
        _cleanup(tarball, proton, tmp, steam_compat)
        return None
    except HTTPException as e:  # Download failed
        log.exception(e)
        return None

    return env


def _update_proton(
    proton: str,
    steam_compat: Path,
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

    log.debug("Previous builds: %s", protons)
    log.debug("Linking UMU-Latest -> %s", proton)
    steam_compat.joinpath("UMU-Latest").unlink(missing_ok=True)
    steam_compat.joinpath("UMU-Latest").symlink_to(proton)

    if not protons:
        return

    for proton in protons:
        if proton.is_dir():
            log.debug("Previous stable build found")
            log.debug("Removing: %s", proton)
            futures.append(thread_pool.submit(rmtree, str(proton)))

    for _ in futures:
        _.result()
