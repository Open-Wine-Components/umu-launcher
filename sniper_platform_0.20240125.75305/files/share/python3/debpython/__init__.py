try:
    from datetime import datetime
except ImportError:
    datetime = None
import logging
import re
from subprocess import PIPE, Popen
from pickle import dumps

log = logging.getLogger(__name__)
PUBLIC_DIR_RE = re.compile(r'.*?/usr/lib/python(\d(?:.\d+)?)/(site|dist)-packages')


class memoize:
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args, **kwargs):
        key = dumps((args, kwargs))
        if key not in self.cache:
            self.cache[key] = self.func(*args, **kwargs)
        return self.cache[key]


def execute(command, cwd=None, env=None, log_output=None):
    """Execute external shell commad.

    :param cdw: currennt working directory
    :param env: environment
    :param log_output:
        * opened log file or path to this file, or
        * None if output should be included in the returned dict, or
        * False if output should be redirectored to stdout/stderr
    """
    args = {'shell': True, 'cwd': cwd, 'env': env}
    close = False
    if log_output is False:
        pass
    elif log_output is None:
        args.update(stdout=PIPE, stderr=PIPE)
    elif log_output:
        if isinstance(log_output, str):
            close = True
            log_output = open(log_output, 'a')
        if datetime:
            log_output.write('\n# command executed on {}'.format(datetime.now().isoformat()))
        log_output.write('\n$ {}\n'.format(command))
        log_output.flush()
        args.update(stdout=log_output, stderr=log_output)

    log.debug('invoking: %s', command)
    with Popen(command, **args) as process:
        stdout, stderr = process.communicate()
        close and log_output.close()
        return dict(returncode=process.returncode,
                    stdout=stdout and str(stdout, 'utf-8'),
                    stderr=stderr and str(stderr, 'utf-8'))
