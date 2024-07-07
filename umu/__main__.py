import sys

from umu.umu_consts import UMU_LOCAL
from umu.umu_log import log
from umu.umu_run import main as umu_run


def main() -> int:  # noqa: D103
    return umu_run()


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
    finally:
        UMU_LOCAL.joinpath(".ref").unlink(
            missing_ok=True
        )  # Cleanup .ref file on every exit
