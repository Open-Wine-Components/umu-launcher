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
from os import walk
from os.path import abspath, isfile, join
from subprocess import Popen, PIPE
from debpython import PUBLIC_DIR_RE

log = logging.getLogger(__name__)


def from_directory(dname, extensions=('.py',)):
    """Generate *.py file names available in given directory."""
    extensions = tuple(extensions)  # .endswith doesn't like list
    if isinstance(dname, (list, tuple)):
        for item in dname:
            for fn in from_directory(item):
                yield fn
    elif isfile(dname) and dname.endswith(extensions):
        yield dname
    else:
        for root, dirs, file_names in walk(abspath(dname)):
            for fn in file_names:
                if fn.endswith(extensions):
                    yield join(root, fn)


def from_package(package_name, extensions=('.py',)):
    """Generate *.py file names available in given package."""
    extensions = tuple(extensions)  # .endswith doesn't like list
    process = Popen("/usr/bin/dpkg -L %s" % package_name,
                    shell=True, stdout=PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise Exception("cannot get content of %s" % package_name)
    stdout = str(stdout, 'utf-8')
    for line in stdout.splitlines():
        if line.endswith(extensions):
            yield line


def filter_directory(files, dname):
    """Generate *.py file names that match given directory."""
    for fn in files:
        if fn.startswith(dname):
            yield fn


def filter_public(files, versions):
    """Generate *.py file names that match given versions."""
    vstr = set("%d.%d" % i for i in versions)
    shared_vstr = set(str(i[0]) for i in versions)
    for fn in files:
        public_dir = PUBLIC_DIR_RE.match(fn)
        if public_dir:
            vers = public_dir.group(1)
            if vers in shared_vstr or vers in vstr:
                yield fn


def filter_out_ext(files, extensions):
    """Removes files with matching extensions from given generator."""
    extensions = tuple(extensions)  # .endswith doesn't like list
    for fn in files:
        if not fn.endswith(extensions):
            yield fn
