#! /usr/bin/python3

import os
import re
import sys

_defaults = None
_old_versions = None
_unsupported_versions = None
_supported_versions = ["python%s" % ver.strip() for ver in
                       os.environ.get('DEBPYTHON3_SUPPORTED', '').split(',')
                       if ver.strip()]
#_default_version = "python%s" % os.environ.get('DEBPYTHON3_DEFAULT', '')
#if _default_version == 'python':
#    _default_version = None
_default_version = None


def read_default(name=None):
    global _defaults
    from configparser import ConfigParser, NoOptionError
    if not _defaults:
        if os.path.exists('/usr/share/python3/debian_defaults'):
            config = ConfigParser()
            defaultsfile = open('/usr/share/python3/debian_defaults')
            config.read_file(defaultsfile)
            defaultsfile.close()
            _defaults = config

    if _defaults and name:
        try:
            value = _defaults.get('DEFAULT', name)
        except NoOptionError:
            raise ValueError
        return value
    return None


def parse_versions(vstring):
    if len(vstring.split(',')) > 2:
        raise ValueError('too many arguments provided for X-Python3-Version: min and max only.')
    import operator
    operators = {None: operator.eq, '=': operator.eq,
                 '>=': operator.ge, '<=': operator.le,
                 '<<': operator.lt}
    vinfo = {}
    exact_versions = set()
    version_range = set(supported_versions(version_only=True))
    relop_seen = False
    for field in vstring.split(','):
        field = field.strip()
        if field == 'all':
            continue
        if field in ('current', 'current_ext'):
            continue
        vinfo.setdefault('versions', set())
        ve = re.compile(r'(>=|<=|<<|=)? *(\d\.\d)$')
        m = ve.match(field)
        try:
            if not m:
                raise ValueError('error parsing Python3-Version attribute')
            op, v = m.group(1), m.group(2)
            vmaj, vmin = v.split('.')
            if int(vmaj) < 3:
                continue
            if op in (None, '='):
                exact_versions.add(v)
            else:
                relop_seen = True
                filtop = operators[op]
                version_range = [av for av in version_range if filtop(av, v)]
        except Exception:
            raise ValueError('error parsing Python3-Version attribute')
    if 'versions' in vinfo:
        vinfo['versions'] = exact_versions
        if relop_seen:
            vinfo['versions'] = exact_versions.union(version_range)
    return vinfo


def old_versions(version_only=False):
    global _old_versions
    if not _old_versions:
        try:
            value = read_default('old-versions')
            _old_versions = [s.strip() for s in value.split(',')]
        except ValueError:
            _old_versions = []
    if version_only:
        return [v[6:] for v in _old_versions]
    else:
        return _old_versions


def unsupported_versions(version_only=False):
    global _unsupported_versions
    if not _unsupported_versions:
        try:
            value = read_default('unsupported-versions')
            _unsupported_versions = [s.strip() for s in value.split(',')]
        except ValueError:
            _unsupported_versions = []
    if version_only:
        return [v[6:] for v in _unsupported_versions]
    else:
        return _unsupported_versions


def supported_versions(version_only=False):
    global _supported_versions,_default_version
    default_version()
    if not _supported_versions:
        try:
            value = read_default('supported-versions')
            _supported_versions = [s.strip() for s in value.split(',')]
        except ValueError:
            cmd = ['/usr/bin/apt-cache', '--no-all-versions',
                   'show', 'python3-all']
            try:
                import subprocess
                p = subprocess.Popen(cmd, bufsize=1,
                                     shell=False, stdout=subprocess.PIPE)
                fd = p.stdout
            except ImportError:
                fd = os.popen(' '.join(cmd))
            depends = None
            for line in fd:
                if line.startswith('Depends:'):
                    depends = line.split(':', 1)[1].strip().split(',')
            fd.close()
            depends = [re.sub(r'\s*(\S+)[ (]?.*', r'\1', s) for s in depends]
            _supported_versions = depends
    default = _supported_versions.pop(_supported_versions.index(_default_version))
    _supported_versions.sort()
    _supported_versions.append(default)
    if version_only:
        return [v[6:] for v in _supported_versions]
    else:
        return _supported_versions


def default_version(version_only=False):
    global _default_version
    if not _default_version:
        _default_version = os.readlink('/usr/bin/python3')
    # consistency check
    debian_default = read_default('default-version')
    if not _default_version in (debian_default, os.path.join('/usr/bin', debian_default)):
        raise ValueError("the symlink /usr/bin/python3 does not point to the "
                         "python3 default version. It must be reset "
                         "to point to %s" % debian_default)
    _default_version = debian_default
    if version_only:
        return _default_version[6:]
    else:
        return _default_version


def requested_versions(vstring, version_only=False):
    global _default_version
    default_version()
    versions = None
    vinfo = parse_versions(vstring)
    supported = supported_versions(version_only=True)
    if len(vinfo) == 1:
        versions = vinfo['versions'].intersection(supported)
        vl = []
        for version in versions: vl.append(version)
        try:
            default = vl.pop(vl.index(_default_version[6:]))
        except:
            default = ''
        vl.sort()
        if default:
            vl.append(default)
    else:
        raise ValueError('No supported python3 versions in version string')
    if not versions:
        raise ValueError('empty set of versions')
    if version_only:
        return vl
    else:
        return ['python%s' % v for v in vl]


def installed_versions(version_only=False):
    import glob
    supported = supported_versions()
    versions = [os.path.basename(s)
                for s in glob.glob('/usr/bin/python3.[0-9]')
                if os.path.basename(s) in supported]
    versions.sort()
    if version_only:
        return [v[6:] for v in versions]
    else:
        return versions


class ControlFileValueError(ValueError):
    pass


class MissingVersionValueError(ValueError):
    pass


def extract_pyversion_attribute(fn, pkg):
    """read the debian/control file, extract the X-Python3-Version
    field."""

    version = None
    sversion = None
    section = None
    with open(fn, encoding='utf-8') as controlfile:
        lines = [line.strip() for line in controlfile]
    for line in lines:
        if line == '' and section != None:
            if pkg == 'Source':
                break
            section = None
        elif line.startswith('Source:'):
            section = 'Source'
        elif line.startswith('Package: ' + pkg):
            section = pkg
        elif line.lower().startswith('x-python3-version:'):
            if section != 'Source':
                raise ValueError('attribute X-Python3-Version not in Source section')
            sversion = line.split(':', 1)[1].strip()
    if section is None:
        raise ControlFileValueError('not a control file')
    if pkg == 'Source':
        if sversion is None:
            raise MissingVersionValueError('no X-Python3-Version in control file')
        return sversion
    return version


'''
def requested_versions_bis(vstring, version_only=False):
    versions = []
    py_supported_short = supported_versions(version_only=True)
    for item in vstring.split(','):
        v=item.split('-')
        if len(v)>1:
            if not v[0]:
                v[0] = py_supported_short[0]
            if not v[1]:
                v[1] = py_supported_short[-1]
            for ver in py_supported_short:
                try:
                    if version_cmp(ver,v[0]) >= 0 \
                           and version_cmp(ver,v[1]) <= 0:
                        versions.append(ver)
                except ValueError:
                    pass
        else:
            if v[0] in py_supported_short:
                versions.append(v[0])
    versions.sort(version_cmp)
    if not versions:
        raise ValueError('empty set of versions')
    if not version_only:
        versions=['python'+i for i in versions]
    return versions
'''


def main():
    from optparse import OptionParser
    usage = '[-v] [-h] [-d|--default] [-s|--supported] [-i|--installed] '
    '[-r|--requested <version string>|<control file>]'
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--default',
                      help='print the default python3 version',
                      action='store_true', dest='default')
    parser.add_option('-s', '--supported',
                      help='print the supported python3 versions',
                      action='store_true', dest='supported')
    parser.add_option('-r', '--requested',
                      help='print the python3 versions requested by a build; '
                           'the argument is either the name of a control file '
                           'or the value of the X-Python3-Version attribute',
                      action='store_true', dest='requested')
    parser.add_option('-i', '--installed',
                      help='print the installed supported python3 versions',
                      action='store_true', dest='installed')
    parser.add_option('-v', '--version',
                      help='print just the version number(s)',
                      default=False, action='store_true', dest='version_only')
    opts, args = parser.parse_args()
    program = os.path.basename(sys.argv[0])

    if opts.default and len(args) == 0:
        try:
            print(default_version(opts.version_only))
        except ValueError as msg:
            print("%s:" % program, msg)
            sys.exit(1)
    elif opts.supported and len(args) == 0:
        print(' '.join(supported_versions(opts.version_only)))
    elif opts.installed and len(args) == 0:
        print(' '.join(installed_versions(opts.version_only)))
    elif opts.requested and len(args) <= 1:
        if len(args) == 0:
            versions = 'debian/control'
        else:
            versions = args[0]
        try:
            if os.path.isfile(versions):
                fn = versions
                try:
                    vstring = extract_pyversion_attribute(fn, 'Source')
                    vs = requested_versions(vstring, opts.version_only)
                except ControlFileValueError:
                    sys.stderr.write("%s: not a control file: %s, "
                                     % (program, fn))
                    sys.exit(1)
                except MissingVersionValueError:
                    sys.stderr.write("%s: no X-Python3-Version in control "
                                     "file, using supported versions\n" %
                                     program)
                    vs = supported_versions(opts.version_only)
            else:
                vs = requested_versions(versions, opts.version_only)
            print(' '.join(vs))
        except ValueError as msg:
            sys.stderr.write("%s: %s\n" % (program, msg))
            sys.exit(1)
    else:
        sys.stderr.write("usage: %s %s\n" % (program, usage))
        sys.exit(1)

if __name__ == '__main__':
    main()
