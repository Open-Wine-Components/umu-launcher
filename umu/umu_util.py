from ctypes.util import find_library
from functools import lru_cache
from shutil import which
from subprocess import PIPE, STDOUT, Popen, TimeoutExpired

from umu_log import log


@lru_cache
def get_libc() -> str:
    """Find libc.so from the user's system."""
    return find_library("c") or ""


def run_zenity(command: str, opts: list[str], msg: str) -> int:
    """Execute the command and pipe the output to zenity.

    Intended to be used for long running operations (e.g. large file downloads)
    """
    bin: str = which("zenity")
    cmd: str = which(command)
    ret: int = 0  # Exit code returned from zenity

    if not bin:
        log.warning("zenity was not found in system")
        return -1
    if not cmd:
        log.warning("%s was not found in system", command)
        return -1

    # Communicate a process with zenity
    with (
        Popen(
            [cmd, *opts],
            stdout=PIPE,
            stderr=STDOUT,
        ) as proc,
        Popen(
            [
                f"{bin}",
                "--progress",
                "--auto-close",
                f"--text={msg}",
                "--percentage=0",
                "--pulsate",
                "--no-cancel",
            ],
            stdin=PIPE,
        ) as zenity_proc,
    ):
        try:
            proc.wait(timeout=300)
        except TimeoutExpired:
            zenity_proc.terminate()
            log.warning("%s timed out after 5 min.", cmd)
            raise TimeoutError
        zenity_proc.stdin.close()
        ret = zenity_proc.wait()

    if ret:
        log.warning("zenity exited with the status code: %s", ret)

    return ret
