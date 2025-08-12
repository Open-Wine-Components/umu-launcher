#!/usr/bin/env python3

import logging
import os
import sys
from argparse import Namespace
from ctypes import CDLL, byref, c_int, create_string_buffer
from ctypes.util import find_library
from logging import getLogger

# Constant defined in prctl.h
# See prctl(2) for more details
PR_SET_CHILD_SUBREAPER = 36
PR_SET_NAME = 15

def get_libc() -> str:
    """Find libc.so from the user's system."""
    return find_library("c") or ""


def subreaper(args: Namespace, other: list[str]) -> int:  # noqa: D103
    logger = getLogger("subreaper")
    logging.basicConfig(
        format="[%(name)s] %(levelname)s: %(message)s",
        level=logging.DEBUG if args.debug else logging.INFO,
        stream=sys.stderr,
    )

    logger.debug("command: %s", args)
    logger.debug("arguments: %s", other)

    command: list[str] = [args.command, *other]
    workdir: str = args.workdir
    child_status: int = 0

    libc: str = get_libc()
    prctl = CDLL(libc).prctl
    prctl.restype = c_int
    prctl.argtypes = [
        c_int,
        # c_ulong,
        # c_ulong,
        # c_ulong,
        # c_ulong,
    ]

    proc_name = b"reaper"
    buff = create_string_buffer(len(proc_name)+1)
    buff.value = proc_name
    prctl_ret = prctl(PR_SET_NAME, byref(buff), 0, 0, 0)
    logger.debug("prctl PR_SET_NAME exited with status: %s", prctl_ret)

    prctl_ret = prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0, 0)
    logger.debug("prctl PR_SET_CHILD_SUBREAPER exited with status: %s", prctl_ret)

    pid = os.fork()  # pylint: disable=E1101
    if pid == -1:
        logger.error("Fork failed")

    if pid == 0:
        sys.stdout.flush()
        sys.stderr.flush()
        os.chdir(workdir)
        os.execvp(command[0], command)  # noqa: S606

    while True:
        try:
            child_pid, child_status = os.wait()  # pylint: disable=E1101
            logger.info("Child %s exited with wait status: %s", child_pid, child_status)
        except ChildProcessError as e:
            logger.info(e)
            break

    return child_status


if __name__ == "__main__":
    sep = sys.argv.index("--")
    argv = sys.argv[sep+1:]
    debug = os.environ.get("UMU_REAPER_DEBUG") in {"1", "debug"}
    args = Namespace(command=argv.pop(0), workdir=os.getcwd(), debug=debug)  # noqa: PTH109
    subreaper(args, argv)


__all__ = ["subreaper"]
