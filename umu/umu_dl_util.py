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
from umu_consts import STEAM_COMPAT
from tempfile import mkdtemp
from threading import Thread

try:
    from tarfile import tar_filter
except ImportError:
    tar_filter: Callable[[str, str], TarInfo] = None


def get_umu_proton(env: Dict[str, str]) -> Union[Dict[str, str]]:
    """Attempt to find existing Proton from the system.

    Downloads the latest if not first found in:
    ~/.local/share/Steam/compatibilitytools.d
    """
    files: List[Tuple[str, str]] = []
    tmp: Path = Path(mkdtemp())
    STEAM_COMPAT.mkdir(exist_ok=True, parents=True)

    try:
        log.debug("Sending request to api.github.com")
        files = _fetch_releases()
    except gaierror:
        log.debug("Network is unreachable")

    # Download the latest Proton
    if _get_latest(env, STEAM_COMPAT, tmp, files):
        return env

    # When offline or an error occurs, use the first Proton in
    # compatibilitytools.d
    if _get_from_steamcompat(env, STEAM_COMPAT):
        return env

    # No internet and compat tool is empty, just return and raise an
    # exception from the caller
    environ["PROTONPATH"] = ""
    return env


def _fetch_releases() -> List[Tuple[str, str]]:
    """Fetch the latest releases from the Github API."""
    files: List[Tuple[str, str]] = []
    resp: HTTPResponse = None
    conn: HTTPConnection = HTTPSConnection(
        "api.github.com", timeout=30, context=create_default_context()
    )
    repo: str = "/repos/Open-Wine-Components/umu-proton/releases"

    if environ.get("PROTONPATH") == "GE-Proton":
        repo = "/repos/GloriousEggroll/proton-ge-custom/releases"

    conn.request(
        "GET",
        repo,
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
    env: Dict[str, str], tmp: Path, files: List[Tuple[str, str]]
) -> Dict[str, str]:
    """Download the latest umu-proton and set it as PROTONPATH."""
    hash, hash_url = files[0]
    proton, proton_url = files[1]
    proton_dir: str = proton[: proton.find(".tar.gz")]  # Proton dir
    ret: int = 0  # Exit code from zenity

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
        with tmp.joinpath(hash).open(mode="wb") as file:
            file.write(resp.read())

    # Proton
    # Create a popup with zenity when the env var is set
    if environ.get("UMU_ZENITY") == "1":
        bin: str = "curl"
        opts: List[str] = [
            "-LJO",
            "--silent",
            proton_url,
            "--output-dir",
            tmp.as_posix(),
        ]
        msg: str = f"Downloading {proton_dir} ..."
        ret = enable_zenity(bin, opts, msg)
        if ret:
            tmp.joinpath(proton).unlink(missing_ok=True)
            log.warning("zenity exited with the status code: %s", ret)
            log.console("Retrying from Python ...")
    if not environ.get("UMU_ZENITY") or ret:
        log.console(f"Downloading {proton} ...")
        with urlopen(  # noqa: S310
            proton_url, timeout=300, context=create_default_context()
        ) as resp:
            # Without Proton, the launcher will not work
            if resp.status != 200:
                err: str = (
                    f"Unable to download {proton}\n"
                    f"github.com returned the status: {resp.status}"
                )
                raise HTTPException(err)
            with tmp.joinpath(proton).open(mode="wb") as file:
                file.write(resp.read())

    log.console("Completed.")

    with tmp.joinpath(proton).open(mode="rb") as file:
        if (
            sha512(file.read()).hexdigest()
            != tmp.joinpath(hash).read_text().split(" ")[0]
        ):
            err: str = "Digests mismatched"
            log.warning(err)
            raise ValueError(err)
        log.console(f"{proton}: SHA512 is OK")

    return env


def _extract_dir(file: Path, steam_compat: Path) -> None:
    """Extract from the cache to another location."""
    with tar_open(file.as_posix(), "r:gz") as tar:
        if tar_filter:
            log.debug("Using filter for archive")
            tar.extraction_filter = tar_filter
        else:
            log.debug("Using no filter for archive")
            log.warning("Archive will be extracted insecurely")

        log.console(f"Extracting {file} -> {steam_compat} ...")
        # TODO: Rather than extracting all of the contents, we should prefer
        # the difference (e.g., rsync)
        tar.extractall(path=steam_compat.as_posix())  # noqa: S202
        log.console("Completed.")


def _cleanup(tarball: str, proton: str, tmp: Path, steam_compat: Path) -> None:
    """Remove files that may have been left in an incomplete state to avoid corruption.

    We want to do this when a download for a new release is interrupted
    """
    log.console("Keyboard Interrupt.\nCleaning ...")

    if tmp.joinpath(tarball).is_file():
        log.console(f"Purging {tarball} in {tmp} ...")
        tmp.joinpath(tarball).unlink()
    if steam_compat.joinpath(proton).is_dir():
        log.console(f"Purging {proton} in {steam_compat} ...")
        rmtree(steam_compat.joinpath(proton).as_posix())


def _get_from_steamcompat(
    env: Dict[str, str], steam_compat: Path
) -> Union[Dict[str, str], None]:
    """Refer to Steam compat folder for any existing Proton directories.

    Executed when an error occurs when retrieving and setting the latest
    Proton
    """
    version: str = (
        "GE-Proton" if environ.get("PROTONPATH") == "GE-Proton" else "UMU-Proton"
    )
    protons: List[Path] = sorted(
        [proton for proton in steam_compat.glob("*") if proton.name.startswith(version)]
    )

    if protons:
        proton: str = protons.pop()
        log.console(f"{proton.name} found in: {steam_compat}")
        log.console(f"Using {proton.name}")
        environ["PROTONPATH"] = proton.as_posix()
        env["PROTONPATH"] = environ["PROTONPATH"]
        return env

    return None


def _get_latest(
    env: Dict[str, str], steam_compat: Path, tmp: Path, files: List[Tuple[str, str]]
) -> Union[Dict[str, str], None]:
    """Download the latest Proton for new installs -- empty cache and Steam compat.

    When the digests mismatched or when interrupted, refer to cache for an old version
    """
    if not files:
        return None

    try:
        tarball: str = files[1][0]
        sums: str = files[0][0]
        proton: str = tarball[: tarball.find(".tar.gz")]
        version: str = (
            "GE-Proton" if environ.get("PROTONPATH") == "GE-Proton" else "UMU-Proton"
        )

        if steam_compat.joinpath(proton).is_dir():
            log.console(f"{version} is up to date")
            environ["PROTONPATH"] = steam_compat.joinpath(proton).as_posix()
            env["PROTONPATH"] = environ["PROTONPATH"]
            return env

        _fetch_proton(env, tmp, files)

        # Set latest UMU/GE-Proton
        if version == "UMU-Proton":
            threads: List[Thread] = []
            log.debug("Updating UMU-Proton")
            old_versions: List[Path] = sorted(
                [
                    file
                    for file in steam_compat.glob("*")
                    if file.name.startswith(("UMU-Proton", "ULWGL-Proton"))
                ]
            )
            tar_path: Path = tmp.joinpath(tarball)

            # Extract the latest archive and update UMU-Proton
            # Will extract and remove the previous stable versions
            # Though, ideally, an in-place differential update would be
            # performed instead for this job but this will do for now
            log.debug("Extracting %s -> %s", tar_path, steam_compat)
            extract: Thread = Thread(target=_extract_dir, args=[tar_path, steam_compat])
            extract.start()
            threads.append(extract)
            update: Thread = Thread(
                target=_update_proton, args=[proton, steam_compat, old_versions]
            )
            update.start()
            threads.append(update)
            for thread in threads:
                thread.join()
        else:
            # For GE-Proton, keep the previous build. Since it's a rebase
            # of bleeding edge, regressions are more likely to occur
            _extract_dir(tmp.joinpath(tarball), steam_compat)

        environ["PROTONPATH"] = steam_compat.joinpath(proton).as_posix()
        env["PROTONPATH"] = environ["PROTONPATH"]

        log.debug("Removing: %s", tarball)
        log.debug("Removing: %s", sums)
        tmp.joinpath(tarball).unlink(missing_ok=True)
        tmp.joinpath(sums).unlink(missing_ok=True)
        log.console(f"Using {version} ({proton})")
    except ValueError:
        log.exception("ValueError")
        tarball: str = files[1][0]

        # Digest mismatched
        # Since we do not want the user to use a suspect file, delete it
        tmp.joinpath(tarball).unlink(missing_ok=True)
        return None
    except KeyboardInterrupt:
        tarball: str = files[1][0]
        proton_dir: str = tarball[: tarball.find(".tar.gz")]  # Proton dir

        # Exit cleanly
        # Clean up extracted data and cache to prevent corruption/errors
        _cleanup(tarball, proton_dir, tmp, steam_compat)
        return None
    except HTTPException:  # Download failed
        log.exception("HTTPException")
        return None

    return env


def _update_proton(proton: str, steam_compat: Path, old_versions: List[Path]) -> None:
    """Create a symbolic link and remove the previous UMU-Proton.

    The symbolic link will be used by clients to reference the PROTONPATH
    which can be used for tasks such as killing the running wineserver in
    the prefix

    Assumes that the directories that are named ULWGL/UMU-Proton is ours
    and will be removed.
    """
    threads: List[Thread] = []
    old: Path = None
    log.debug("Old: %s", old_versions)
    log.debug("Linking UMU-Latest -> %s", proton)
    steam_compat.joinpath("UMU-Latest").unlink(missing_ok=True)
    steam_compat.joinpath("UMU-Latest").symlink_to(proton)

    if not old_versions:
        return

    old = old_versions.pop()
    if old.is_dir():
        log.debug("Removing: %s", old)
        oldest: Thread = Thread(target=rmtree, args=[old.as_posix()])
        oldest.start()
        threads.append(oldest)

    for proton in old_versions:
        if proton.is_dir():
            log.debug("Old stable build found")
            log.debug("Removing: %s", proton)
            sibling: Thread = Thread(target=rmtree, args=[proton.as_posix()])
            sibling.start()
            threads.append(sibling)

    for thread in threads:
        thread.join()
