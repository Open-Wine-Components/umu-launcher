import subprocess


def get_steam_compat_lib():
    """Find the library paths of a system.

    Used for Steam's game drive
    """
    ldconfig_cmd = ["ldconfig", "-XNv"]
    grep_cmd = ["grep", "^/.*:"]
    paths = ""

    try:
        # TODO: Not ideal. Find a way to accomplish this simply in pure Python
        result = subprocess.run(
            ldconfig_cmd,
            capture_output=True,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )
        result = subprocess.run(
            grep_cmd, input=result.stdout, text=True, check=True, capture_output=True
        )

        for line in result.stdout.splitlines():
            if not paths:
                paths += line.split(":")[0]
            else:
                paths += ":" + line.split(":")[0]

        return paths
    except subprocess.CalledProcessError as err:
        status = err.returncode
        cmd = " ".join(ldconfig_cmd + grep_cmd)
        err = "An error occurred while executing {}: {}".format(cmd, status)
        raise subprocess.CalledProcessError(err)


def get_steam_compat_install(envar):
    """Find the mnt point of filesystem path.

    Used for Steam's game drive
    Expects envar to be STEAM_COMPAT_INSTALL_PATH
    """
    findmnt_cmd = ["findmnt", "-T", envar]
    tail_cmd = ["tail", "-n", "1"]
    awk_cmd = ["awk", "{ print $1 }"]

    try:
        # TODO: Not ideal. Find a way to accomplish this simply in pure Python
        result = subprocess.run(findmnt_cmd, capture_output=True, text=True, check=True)
        result = subprocess.run(
            tail_cmd, input=result.stdout, capture_output=True, text=True, check=True
        )
        result = subprocess.run(
            awk_cmd, input=result.stdout, capture_output=True, text=True, check=True
        )

        if result.stdout.strip() == "/":
            return ""
        return result.stdout.strip()

    except subprocess.CalledProcessError as err:
        status = err.returncode
        cmd = " ".join(findmnt_cmd + tail_cmd + awk_cmd)
        err = "An error occurred while executing {}: {}".format(cmd, status)
        raise subprocess.CalledProcessError(err)
