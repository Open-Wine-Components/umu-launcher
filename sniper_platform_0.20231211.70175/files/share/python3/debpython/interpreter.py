# Copyright © 2012 Piotr Ożarowski <piotr@debian.org>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import logging
import os
import re
from os.path import join, split
from debpython import execute
from debpython.version import Version

SHEBANG_RE = re.compile(r'''
    (?:\#!\s*){0,1}  # shebang prefix
    (?P<path>
        .*?/bin/.*?)?
    (?P<name>
        python|pypy)
    (?P<version>
        \d[\.\d]*)?
    (?P<debug>
        -dbg)?
    (?P<options>.*)
    ''', re.VERBOSE)
EXTFILE_RE = re.compile(r'''
    (?P<name>.*?)
    (?:\.
        (?P<stableabi>abi\d+)
     |(?:\.
        (?P<soabi>
            (?P<impl>cpython|pypy)
            -
            (?P<ver>\d{2})
            (?P<flags>[a-z]*?)
        )
        (?:
            -(?P<multiarch>[^/]*?)
        )?
    ))?
    (?P<debug>_d)?
    \.so$''', re.VERBOSE)
log = logging.getLogger(__name__)


class Interpreter:
    path = None
    name = 'python'
    version = None
    debug = False
    impl = 'cpython'  # implementation
    options = ()
    _cache = {}

    def __init__(self, value=None, path=None, name=None, version=None,
                 debug=None, impl=None, options=None):
        params = locals()
        del params['self']
        del params['value']

        if isinstance(value, Interpreter):
            for key in params.keys():
                if params[key] is None:
                    params[key] = getattr(value, key)
        elif value:
            if value.replace('.', '').isdigit() and not version:
                params['version'] = Version(value)
            else:
                for key, val in self.parse(value).items():
                    if params[key] is None:
                        params[key] = val

        for key, val in params.items():
            setattr(self, key, val)

    def __setattr__(self, name, value):
        if name == 'name' and value:
            if value.startswith('python'):
                self.__dict__['impl'] = 'cpython'
            elif value.startswith('pypy'):
                self.__dict__['impl'] = 'pypy'
            if '-dbg' in value:
                self.__dict__['debug'] = True
        elif name == 'version' and value is not None:
            value = Version(value)
        if name in ('name', 'impl', 'debug', 'options') and value is None:
            # get the class default instead
            self.__dict__[name] = getattr(Interpreter, name)
        else:
            self.__dict__[name] = value

    def __repr__(self):
        result = self.path or ''
        result += self._vstr(self.version)
        if self.options:
            result += ' ' + ' '.join(self.options)
        return result

    def __str__(self):
        return self._vstr(self.version)

    def _vstr(self, version):
        if self.impl == 'pypy':
            # TODO: will Debian support more than one PyPy version?
            return self.name
        if version and str(version) not in self.name:
            if self.debug:
                return 'python{}-dbg'.format(version)
            return self.name + str(version)
        return self.name

    @staticmethod
    def parse(shebang):
        """Return dict with parsed shebang

        >>> sorted(Interpreter.parse('pypy').items())
        [('debug', None), ('name', 'pypy'), ('options', ()), ('path', None), ('version', None)]
        >>> sorted(Interpreter.parse('/usr/bin/python3.3-dbg').items())
        [('debug', '-dbg'), ('name', 'python'), ('options', ()), ('path', '/usr/bin/'), ('version', '3.3')]
        >>> sorted(Interpreter.parse('#! /usr/bin/pypy --foo').items())
        [('debug', None), ('name', 'pypy'), ('options', ('--foo',)), ('path', '/usr/bin/'), ('version', None)]
        >>> sorted(Interpreter.parse('#! /usr/bin/python3.2').items())
        [('debug', None), ('name', 'python'), ('options', ()), ('path', '/usr/bin/'), ('version', '3.2')]
        >>> sorted(Interpreter.parse('/usr/bin/python3.2-dbg --foo --bar').items())
        [('debug', '-dbg'), ('name', 'python'), ('options', ('--foo', '--bar')),\
 ('path', '/usr/bin/'), ('version', '3.2')]
        """
        result = SHEBANG_RE.search(shebang)
        if not result:
            return {}
        result = result.groupdict()
        if 'options' in result:
            # TODO: do we need "--key value" here?
            result['options'] = tuple(result['options'].split())
        return result

    def sitedir(self, gdb=False, package=None, version=None):
        """Return path to site-packages directory.

        Note that returned path is not the final location of .py files

        >>> i = Interpreter('python')
        >>> i.sitedir(version='3.1')
        '/usr/lib/python3/dist-packages/'
        >>> i.sitedir(version='2.5')
        '/usr/lib/python2.5/site-packages/'
        >>> i.sitedir(version=Version('2.7'))
        '/usr/lib/python2.7/dist-packages/'
        >>> i.sitedir(version='3.1', gdb=True, package='python3-foo')
        'debian/python3-foo/usr/lib/debug/usr/lib/python3/dist-packages/'
        >>> i.sitedir(version=Version('3.2'))
        '/usr/lib/python3/dist-packages/'
        >>> Interpreter('pypy').sitedir(version='2.0')
        '/usr/lib/pypy/dist-packages/'
        """
        version = Version(version or self.version)
        #if not version:
        #    version = Version(DEFAULT)
        if self.impl == 'pypy':
            path = '/usr/lib/pypy/dist-packages/'
        elif version << Version('2.6'):
            path = "/usr/lib/python%s/site-packages/" % version
        elif version << Version('3.0'):
            path = "/usr/lib/python%s/dist-packages/" % version
        else:
            path = '/usr/lib/python3/dist-packages/'

        if gdb:
            path = "/usr/lib/debug%s" % path
        if package:
            path = "debian/%s%s" % (package, path)

        return path

    def cache_file(self, fpath, version=None):
        """Given path to a .py file, return path to its .pyc/.pyo file.

        This function is inspired by Python 3.2's imp.cache_from_source.

        :param fpath: path to file name
        :param version: Python version

        >>> i = Interpreter('python')
        >>> i.cache_file('foo.py', Version('3.1'))
        'foo.pyc'
        >>> i.cache_file('bar/foo.py', '3.2')
        'bar/__pycache__/foo.cpython-32.pyc'
        """
        version = Version(version or self.version)
        last_char = 'o' if '-O' in self.options else 'c'
        if version <= Version('3.1'):
            return fpath + last_char

        fdir, fname = split(fpath)
        if not fname.endswith('.py'):
            fname += '.py'
        return join(fdir, '__pycache__', "%s.%s.py%s" %
                    (fname[:-3], self.magic_tag(version), last_char))

    def ext_file(self, name, version=None):
        """Return extension name with soname and multiarch tags."""
        version = Version(version or self.version)
        soabi, multiarch = self._get_config(version)
        result = name.split('.', 1)[0]
        if soabi:
            result += '.{}'.format(soabi)
            if multiarch:
                result += '-{}'.format(multiarch)
        if self.debug and self.impl == 'cpython'\
                and version << Version('3'):
            result += '_d'
        return '{}.so'.format(result)

    def magic_number(self, version=None):
        """Return magic number."""
        version = Version(version or self.version)
        if self.impl == 'cpython' and version << Version('3'):
            return ''
        result = self._execute('import imp; print(imp.get_magic())', version)
        return eval(result)

    def magic_tag(self, version=None):
        """Return Python magic tag (used in __pycache__ dir to tag files).

        >>> i = Interpreter('python')
        >>> i.magic_tag(version='3.2')
        'cpython-32'
        """
        version = Version(version or self.version)
        if self.impl == 'cpython' and version << Version('3.2'):
            return ''
        return self._execute('import imp; print(imp.get_tag())', version)

    def multiarch(self, version=None):
        """Return multiarch tag."""
        version = Version(version or self.version)
        try:
            soabi, multiarch = self._get_config(version)
        except Exception:
            log.debug('cannot get multiarch', exc_info=True)
            # interpreter without multiach support
            return ''
        return multiarch

    def stableabi(self, version=None):
        version = Version(version or self.version)
        # stable ABI was introduced in Python 3.3
        if self.impl == 'cpython' and version >> Version('3.2'):
            return 'abi{}'.format(version.major)

    def soabi(self, version=None):
        """Return SOABI flag (used to in .so files).

        >>> i = Interpreter('python')
        >>> i.soabi(version=Version('3.3'))
        'cpython-33m'
        """
        version = Version(version or self.version)
        # NOTE: it's not the same as magic_tag
        try:
            soabi, multiarch = self._get_config(version)
        except Exception:
            log.debug('cannot get soabi', exc_info=True)
            # interpreter without soabi support
            return ''
        return soabi

    def check_extname(self, fname, version=None):
        """Return extension file name if file can be renamed.

        >>> i = Interpreter('python')
        >>> i.check_extname('foo.so', version='3.3') # doctest: +ELLIPSIS
        'foo.cpython-33m-....so'
        >>> i.check_extname('foo.abi3.so', version='3.3')
        >>> i.check_extname('foo/bar/bazmodule.so', version='3.3') # doctest: +ELLIPSIS
        'foo/bar/baz.cpython-33m-....so'
        """
        version = Version(version or self.version)

        if '/' in fname:
            fdir, fname = fname.rsplit('/', 1)  # in case full path was passed
        else:
            fdir = ''

        info = EXTFILE_RE.search(fname)
        if not info:
            return
        info = info.groupdict()

        if info['stableabi']:
            # files with stable ABI in name don't need changes
            return

        i = Interpreter(self, version=version)
        if info['ver']:
            i.version = "{}.{}".format(info['ver'][0], info['ver'][1])
        if not i.debug and (info['debug'] or 'd' in (info['flags'] or '')):
            i.debug = True
        try:
            soabi, multiarch = i._get_config()
        except Exception:
            log.debug('cannot get soabi/multiarch', exc_info=True)
            return
        result = info['name']
        if i.impl == 'cpython' and i.version >> '3.2' and result.endswith('module'):
            result = result[:-6]
        if info['soabi'] or soabi:
            result = "{}.{}".format(result, info['soabi'] or soabi)
            if info['multiarch'] or multiarch:
                result = "{}-{}".format(result, info['multiarch'] or multiarch)

        result += '.so'
        if fname == result:
            return
        return join(fdir, result)

    def _get_config(self, version=None):
        version = Version(version or self.version)
        # sysconfig module is available since Python 3.2
        # (also backported to Python 2.7)
        if self.impl == 'pypy' or self.impl == 'cpython' and (
                version >> '2.6' and version << '3'
                or version >> '3.1' or version == '3'):
            cmd = 'import sysconfig as s;'
        else:
            cmd = 'from distutils import sysconfig as s;'
        cmd += 'print("__SEP__".join(i or "" ' \
               'for i in s.get_config_vars("SOABI", "MULTIARCH")))'
        conf_vars = self._execute(cmd, version).split('__SEP__')
        try:
            conf_vars[1] = os.environ['DEB_HOST_MULTIARCH']
        except KeyError:
            pass
        return conf_vars

    def _execute(self, command, version=None, cache=True):
        version = Version(version or self.version)
        command = "{} -c '{}'".format(self._vstr(version), command.replace("'", "\'"))
        if cache and command in self.__class__._cache:
            return self.__class__._cache[command]

        output = execute(command)
        if output['returncode'] != 0:
            log.debug(output['stderr'])
            raise Exception('{} failed with status code {}'.format(command, output['returncode']))

        result = output['stdout'].splitlines()

        if len(result) == 1:
            result = result[0]

        if cache:
            self.__class__._cache[command] = result

        return result
