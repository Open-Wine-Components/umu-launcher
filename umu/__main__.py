import os
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter

from umu import __version__
from umu.umu_consts import PROTON_VERBS, UMU_LOCAL
from umu.umu_log import log
from umu.umu_run import umu_run
from umu.umu_util import is_winetricks_verb


def parse_args() -> Namespace | tuple[str, list[str]]:  # noqa: D103
    opt_args: set[str] = {"--help", "-h", "--config"}
    parser: ArgumentParser = ArgumentParser(
        description="Unified Linux Wine Game Launcher",
        epilog=(
            "See umu(1) for more info and examples, or visit\n"
            "https://github.com/Open-Wine-Components/umu-launcher"
        ),
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--version",
        action="store_true",
        help="show this version and exit",
    )
    parser.add_argument(
        "--config", help=("path to TOML file (requires Python 3.11+)")
    )
    parser.add_argument(
        "winetricks",
        help=("run winetricks verbs (requires UMU-Proton or GE-Proton)"),
        nargs="?",
        default=None,
    )

    if not sys.argv[1:]:
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Show version
    # Need to avoid clashes with later options (for example: wineboot -u)
    #   but parse_args scans the whole command line.
    # So look at the first argument and see if we have -v or --version
    #   in sort of the same way parse_args would.
    if sys.argv[1].lower().endswith(("--version", "-v")):
        print(
            f"umu-launcher version {__version__} ({sys.version})",
            file=sys.stderr,
        )
        sys.exit(0)

    # Winetricks
    # Exit if no winetricks verbs were passed
    if sys.argv[1].endswith("winetricks") and not sys.argv[2:]:
        err: str = "No winetricks verb specified"
        log.error(err)
        sys.exit(1)

    # Exit if argument is not a verb
    if sys.argv[1].endswith("winetricks") and not is_winetricks_verb(
        sys.argv[2:]
    ):
        sys.exit(1)

    if sys.argv[1:][0] in opt_args:
        return parser.parse_args(sys.argv[1:])

    if sys.argv[1] in PROTON_VERBS:
        if "PROTON_VERB" not in os.environ:
            os.environ["PROTON_VERB"] = sys.argv[1]
        sys.argv.pop(1)

    return sys.argv[1], sys.argv[2:]


def main() -> int:  # noqa: D103
    args: Namespace | tuple[str, list[str]] = parse_args()

    # Adjust logger for debugging when configured
    if os.environ.get("UMU_LOG") in {"1", "debug"}:
        log.setLevel(level="DEBUG")
        log.set_formatter(os.environ["UMU_LOG"])
        for key, val in os.environ.items():
            log.debug("%s=%s", key, val)

    if os.geteuid() == 0:
        err: str = "This script should never be run as the root user"
        log.error(err)
        sys.exit(1)

    if "musl" in os.environ.get("LD_LIBRARY_PATH", ""):
        err: str = "This script is not designed to run on musl-based systems"
        log.error(err)
        sys.exit(1)

    return umu_run(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("Keyboard Interrupt")
    except SystemExit as e:
        if e.code:
            sys.exit(e.code)
    except BaseException as e:
        log.exception(e)
