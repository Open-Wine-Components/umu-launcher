#!/usr/bin/env python3

# Copyright © 2019-2022 Collabora Ltd.
#
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import argparse
import contextlib
import logging
import os
import shlex
import subprocess
import sys

try:
    import typing
except ImportError:
    pass

import gi
gi.require_version('Gtk', '3.0')

# Ignore E402: import not at top of file. gi.require_version() must come first
from gi.repository import GLib      # noqa: E402
from gi.repository import Gtk       # noqa: E402

logger = logging.getLogger('steam-runtime-launch-options')

assert sys.version_info >= (3, 4), 'Python 3.4+ is required for this script'

# Linux runtime environments we can target with the Steam Runtime.
# Traditionally, all native Linux games have run in a scout environment,
# variously referred to as 'linux' or 'ubuntu12_32' by Steam.
RUNTIMES = [
    'scout',    # Steam Runtime 1 'scout', based on Ubuntu 12.04
    'heavy',    # Steam Runtime 1½ 'heavy', based on Debian 8
    'soldier',  # Steam Runtime 2 'soldier', based on Debian 10
    'sniper',   # Steam Runtime 3 'sniper', based on Debian 11
    'medic',    # Steam Runtime 4 'medic', provisionally based on Debian 12
    'steamrt5',     # Steam Runtime 5, provisionally based on Debian 13
]

# All available compatibility targets, including Windows (via Proton)
# and native Linux (whatever the host system happens to be running, e.g.
# SteamOS, Debian, Arch, Fedora).
COMPAT_TARGETS = RUNTIMES + ['windows', 'host']


def tristate_environment(name):
    # type: (str) -> typing.Optional[bool]
    value = os.getenv(name)

    if value is None or value == '':
        return None

    if value == '1':
        return True

    if value == '0':
        return False

    logger.warning('Unrecognised value %r for $%s', value, name)
    return None


def boolean_environment(name, default):
    # type: (str, bool) -> bool
    value = os.getenv(name)

    if value is None:
        return default

    if value == '1':
        return True

    if value in ('', '0'):
        return False

    logger.warning('Unrecognised value %r for $%s', value, name)
    return default


def to_shell(argv):
    # type: (typing.Iterable[str]) -> str
    return ' '.join(map(shlex.quote, argv))


class Component:
    def __init__(
        self,
        path,                           # type: str
        home,                           # type: str
    ):  # type: (...) -> None
        self.home = home
        self.path = path

        self.argv = []                  # type: typing.List[str]
        self.description = ''
        self.runs_on = ''


class App(Component):
    def __init__(
        self,
        path,                           # type: str
        home,                           # type: str
        argv,                           # type: typing.List[str]
    ):  # type: (...) -> None
        super().__init__(path, home=home)
        self.argv = argv
        self.description = 'App or game to run'
        self.runs_on = 'scout'


class Proton(Component):
    def __init__(
        self,
        path,                           # type: str
        home,                           # type: str
        argv,                           # type: typing.List[str]
    ):  # type: (...) -> None
        super().__init__(path, home=home)
        self.argv = argv

        if path.startswith(self.home + '/'):
            path = '~' + path[len(self.home):]

        version = os.path.basename(self.path)
        self.description = '{}\n({})'.format(version or '(unknown)', path)

        # TODO: Parse this with python3-vdf?
        try:
            with open(os.path.join(self.path, 'toolmanifest.vdf')) as reader:
                content = reader.read().strip()
        except Exception:
            logger.debug('Failed to get Proton tool manifest', exc_info=True)
            content = ''

        if '1391110' in content:
            self.runs_on = 'soldier'
        elif '1628350' in content:
            self.runs_on = 'sniper'
        else:
            self.runs_on = 'scout'


class PressureVessel(Component):
    def __init__(
        self,
        path,                           # type: str
        home,                           # type: str
    ):  # type: (...) -> None
        super().__init__(path, home=home)

        if path.startswith(self.home + '/'):
            path = '~' + path[len(self.home):]

        try:
            subproc = subprocess.Popen(
                [
                    os.path.join(
                        self.path,
                        'bin',
                        'pressure-vessel-wrap'
                    ),
                    '--version-only',
                ],
                stdout=subprocess.PIPE,
            )
            stdout, _ = subproc.communicate()
            version = stdout.decode('utf-8', errors='replace').strip()
        except Exception:
            logger.debug(
                'Failed to run %s/bin/pressure-vessel-wrap --version-only',
                self.path,
                exc_info=True,
            )
            version = ''

        self.adverb = os.path.join(
            self.path, 'bin', 'pressure-vessel-adverb',
        )
        self.description = '{}\n({})'.format(version or '(unknown)', path)
        self.unruntime = os.path.join(
            self.path, 'bin', 'pressure-vessel-unruntime',
        )
        self.version = version


class Runtime(Component):
    def __init__(
        self,
        path,                           # type: str
        home,                           # type: str
    ):  # type: (...) -> None
        super().__init__(path, home=home)

        self.provides = ''


class LdlpRuntime(Runtime):
    def __init__(
        self,
        path,           # type: str
        home,           # type: str
    ):  # type: (...) -> None
        super().__init__(path, home=home)

        try:
            with open(os.path.join(path, 'version.txt')) as reader:
                version = reader.read().strip()
        except Exception:
            logger.debug('Failed to get LDLP runtime version', exc_info=True)
            version = ''

        if version.startswith('steam-runtime-heavy_'):
            version = 'heavy ' + version[len('steam-runtime-heavy_'):]

            if not self.provides:
                self.provides = 'heavy'
        elif version.startswith('steam-runtime_'):
            version = 'scout ' + version[len('steam-runtime_'):]

            if not self.provides:
                self.provides = 'scout'

        if path.startswith(self.home + '/'):
            path = '~' + path[len(self.home):]

        self.description = '{}\n({})'.format(
            version or '(unknown version)',
            path,
        )

        self.argv = [
            os.path.join(self.path, 'scripts', 'switch-runtime.sh'),
            '--runtime=' + self.path,
            '--',
        ]


class LaunchWrapper(Component):
    def __init__(
        self,
        path,           # type: str
        home,           # type: str
        argv,           # type: typing.List[str]
    ):  # type: (...) -> None
        super().__init__(path, home=home)
        self.argv = argv


class Reaper(Component):
    def __init__(
        self,
        path,           # type: str
        home,           # type: str
        argv,           # type: typing.List[str]
    ):  # type: (...) -> None
        super().__init__(path, home=home)
        self.argv = argv


class LayeredRuntime(LdlpRuntime):
    def __init__(
        self,
        path,           # type: str
        home,           # type: str
        argv,           # type: typing.List[str]
    ):  # type: (...) -> None
        super().__init__(path, home=home)
        self.argv = argv

        if path.startswith(self.home + '/'):
            path = '~' + path[len(self.home):]

        self.description = path
        self.provides = 'scout'
        self.runs_on = 'soldier'


class ContainerRuntime(Runtime):
    def get_sort_weight(
        self,
        default=''      # type: str
    ):  # type: (...) -> typing.Any
        return (0,)

    def _runtime_version(self):
        # type: (...) -> typing.Any
        if self.provides.startswith('steamrt'):
            return int(self.provides[len('steamrt'):])

        return {
            'scout': 1,
            'heavy': 1.5,
            'soldier': 2,
            'sniper': 3,
            'medic': 4,
        }.get(self.provides, 0)


class ContainerRuntimeDepot(ContainerRuntime):
    def __init__(
        self,
        path,           # type: str
        home,           # type: str
        argv,           # type: typing.List[str]
    ):  # type: (...) -> None
        super().__init__(path, home=home)
        self.argv = argv

        if path.startswith(self.home + '/'):
            path = '~' + path[len(self.home):]

        try:
            self.description = self.__describe_runtime(path)
        except Exception:
            logger.debug('Failed to get runtime info', exc_info=True)
            self.description = os.path.basename(path)

        self.description = '{}\n({})'.format(self.description, path)

        self.pressure_vessel = None     # type: typing.Optional[PressureVessel]
        self.var_path = os.path.join(self.path, 'var')

        try:
            pv = PressureVessel(
                os.path.join(self.path, 'pressure-vessel'),
                home=home,
            )
        except Exception:
            logger.debug('Failed to get PV info', exc_info=True)
        else:
            self.pressure_vessel = pv

    def get_sort_weight(self, default):
        if default == self.provides:
            weight = -10
        else:
            weight = -1

        return (weight, self._runtime_version(), self.path)

    def __describe_runtime(
        self,
        path            # type: str
    ):
        # type: (...) -> str

        platform = ['', '']
        depot_version = ''

        with open(os.path.join(self.path, 'VERSIONS.txt')) as reader:
            for row in reader:
                if row.startswith('#'):
                    continue

                if row.startswith('depot\t'):
                    depot_version = row.split('\t')[1]

                if row.startswith(('soldier\t', 'sniper\t')):
                    platform = row.split('\t')[:1]

        if platform[0]:
            self.provides = platform[0]
            return platform[0] + ' ' + (depot_version or platform[1])

        return '(unknown)'


class DirectoryRuntime(ContainerRuntime):
    def __init__(
        self,
        path,           # type: str
        home,           # type: str
    ):  # type: (...) -> None
        super().__init__(path, home=home)

        self.description = self.__describe_runtime(path)

    def get_sort_weight(self, default):
        return (1, self._runtime_version(), self.path)

    def __describe_runtime(
        self,
        path        # type: str
    ):
        # type: (...) -> str

        description = path
        files = os.path.join(self.path, 'files')
        metadata = os.path.join(self.path, 'metadata')

        if os.path.islink(files):
            description = os.path.realpath(files)

        if description.startswith(self.home + '/'):
            description = '~' + description[len(self.home):]

        name = None             # type: typing.Optional[str]
        pretty_name = None      # type: typing.Optional[str]
        build_id = None         # type: typing.Optional[str]
        variant = None          # type: typing.Optional[str]

        try:
            keyfile = GLib.KeyFile.new()
            keyfile.load_from_file(
                metadata, GLib.KeyFileFlags.NONE)
            try:
                build_id = keyfile.get_string('Runtime', 'x-flatdeb-build-id')
            except GLib.Error:
                pass

            try:
                name = keyfile.get_string('Runtime', 'runtime')
            except GLib.Error:
                pass
            else:
                assert name is not None
                variant = name.split('.')[-1]
        except GLib.Error:
            pass

        try:
            with open(
                os.path.join(files, 'lib', 'os-release')
            ) as reader:
                for line in reader:
                    if line.startswith('PRETTY_NAME='):
                        pretty_name = line.split('=', 1)[1].strip()
                        pretty_name = GLib.shell_unquote(pretty_name)
                    elif line.startswith('BUILD_ID='):
                        build_id = line.split('=', 1)[1].strip()
                        build_id = GLib.shell_unquote(build_id)
                    elif line.startswith('VARIANT='):
                        variant = line.split('=', 1)[1].strip()
                        variant = GLib.shell_unquote(variant)
        except (GLib.Error, EnvironmentError):
            pass

        if pretty_name is None:
            pretty_name = name

        if pretty_name is None:
            pretty_name = os.path.basename(path)

        if build_id is None:
            build_id = ''
        else:
            build_id = ' build {}'.format(build_id)

        if variant is None:
            variant = ''
        else:
            variant = ' {}'.format(variant)

        description = '{}{}{}\n({})'.format(
            pretty_name,
            variant,
            build_id,
            description,
        )

        return description


class ArchiveRuntime(ContainerRuntime):
    def __init__(
        self,
        path,           # type: str
        buildid_file,   # type: str
        home,           # type: str
    ):  # type: (...) -> None
        super().__init__(path, home=home)

        if path.startswith(self.home + '/'):
            path = '~' + path[len(self.home):]

        description = os.path.basename(path)
        sdk_suffix = ''

        if description.startswith('com.valvesoftware.SteamRuntime.'):
            description = description[len('com.valvesoftware.SteamRuntime.'):]

        if description.startswith('Platform-'):
            description = description[len('Platform-'):]

        if description.startswith('Sdk-'):
            sdk_suffix = '-sdk'
            description = description[len('Sdk-'):]

        if description.startswith('amd64,i386-'):
            description = description[len('amd64,i386-'):]

        if description.endswith('.tar.gz'):
            description = description[:-len('.tar.gz')]

        if description.endswith('-runtime'):
            description = description[:-len('-runtime')]

        with open(buildid_file) as reader:
            build = reader.read().strip()

        self.deploy_id = '{}{}_{}'.format(description, sdk_suffix, build)
        self.description = '{} build {}\n({})'.format(description, build, path)

    def get_sort_weight(self, default):
        return (2, self._runtime_version(), self.path)


class Gui:
    def __init__(self):
        # type: (...) -> None

        self.steam_runtime_env = {}     # type: typing.Dict[str, str]
        self.failed = False
        self.home = GLib.get_home_dir()
        self.app = App(path='', argv=[], home=self.home)
        self.launch_wrapper = None      # type: typing.Optional[LaunchWrapper]
        self.reaper = None              # type: typing.Optional[Reaper]
        self.default_container_runtime = (
            None
        )   # type: typing.Optional[ContainerRuntimeDepot]
        self.default_pressure_vessel = (
            None
        )   # type: typing.Optional[PressureVessel]
        self.default_layered_runtime = (
            None
        )   # type: typing.Optional[LayeredRuntime]
        self.default_proton = (
            None
        )   # type: typing.Optional[Proton]

        self.container_runtimes = {
        }    # type: typing.Dict[str, ContainerRuntime]

        self.pressure_vessels = {
        }    # type: typing.Dict[str, PressureVessel]

        self.layered_runtimes = {
        }    # type: typing.Dict[str, LayeredRuntime]

        self.ldlp_runtimes = {
        }    # type: typing.Dict[str, LdlpRuntime]

        self.proton_versions = {
        }    # type: typing.Dict[str, Proton]

        self._changing = 0
        self._changing_container_runtime = 0
        self._container_runtime_changed_id = 0
        self._layered_runtime_changed_id = 0
        self._pressure_vessel_changed_id = 0
        self._ldlp_runtime_changed_id = 0
        self._proton_changed_id = 0

        self.window = Gtk.Window()
        self.window.set_default_size(720, 480)
        self.window.connect('delete-event', Gtk.main_quit)
        self.window.set_title('Launch options')

        self.vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)
        self.window.add(self.vbox)

        row = 0

        self.grid = Gtk.Grid(
            row_spacing=6,
            column_spacing=6,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        scrolled_window = Gtk.ScrolledWindow.new(None, None)
        scrolled_window.add(self.grid)
        if hasattr(scrolled_window.props, 'propagate_natural_width'):
            scrolled_window.props.propagate_natural_width = True
            scrolled_window.props.propagate_natural_height = True
        scrolled_window.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        self.vbox.pack_start(scrolled_window, True, True, 0)

        label = Gtk.Label.new('')
        label.set_markup(
            'This is a test UI for developers. '
            '<b>'
            'Some options are known to break games and Steam features.'
            '</b>'
            ' Use at your own risk!'
        )
        label.set_line_wrap(True)
        self.grid.attach(label, 0, row, 3, 1)
        row += 1

        label = Gtk.Label.new('Container runtime')
        self.grid.attach(label, 0, row, 1, 1)

        self.container_runtime_combo = Gtk.ComboBoxText.new()
        self.grid.attach(self.container_runtime_combo, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('Variable data path')
        self.grid.attach(label, 0, row, 1, 1)
        self.var_path_entry = Gtk.Entry.new()
        self.var_path_entry.props.editable = False
        self.var_path_entry.props.has_frame = False
        self.var_path_entry.props.hexpand = True
        self.grid.attach(self.var_path_entry, 1, row, 1, 1)
        self.var_path_browse = Gtk.Button.new_with_label('Browse...')
        self.var_path_browse.connect('clicked', self.var_path_browse_cb)
        self.var_path_browse.props.hexpand = False
        self.grid.attach(self.var_path_browse, 2, row, 1, 1)

        row += 1

        label = Gtk.Label.new('pressure-vessel')
        self.grid.attach(label, 0, row, 1, 1)

        self.pressure_vessel_combo = Gtk.ComboBoxText.new()
        self.grid.attach(self.pressure_vessel_combo, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('Layered runtime scripts')
        self.grid.attach(label, 0, row, 1, 1)

        self.layered_runtime_combo = Gtk.ComboBoxText.new()
        self.grid.attach(self.layered_runtime_combo, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('LD_LIBRARY_PATH runtime')
        self.grid.attach(label, 0, row, 1, 1)

        self.ldlp_runtime_combo = Gtk.ComboBoxText.new()
        self.grid.attach(self.ldlp_runtime_combo, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('Proton')
        self.grid.attach(label, 0, row, 1, 1)

        self.proton_combo = Gtk.ComboBoxText.new()
        self.grid.attach(self.proton_combo, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('SDL video driver')
        self.grid.attach(label, 0, row, 1, 1)

        self.sdl_videodriver_combo = Gtk.ComboBoxText.new()
        self.sdl_videodriver_combo.append(None, "Don't override")
        self.sdl_videodriver_combo.append('wayland', 'Wayland')
        self.sdl_videodriver_combo.append('x11', 'X11')
        self.sdl_videodriver_combo.set_active(0)
        self.grid.attach(self.sdl_videodriver_combo, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('Graphics stack')
        self.grid.attach(label, 0, row, 1, 1)

        self.graphics_provider_combo = Gtk.ComboBoxText.new()
        self.graphics_provider_combo.append(None, "Don't override")

        env = os.getenv('PRESSURE_VESSEL_GRAPHICS_PROVIDER')

        if env is not None:
            self.graphics_provider_combo.append(
                env,
                '$PRESSURE_VESSEL_GRAPHICS_PROVIDER ({})'.format(
                    env or 'empty'
                ),
            )

        if env is None or env != '/':
            self.graphics_provider_combo.append(
                '/', 'Current execution environment',
            )

        if (
            (env is None or env != '/run/host')
            and os.path.isdir('/run/host/etc')
            and os.path.isdir('/run/host/usr')
        ):
            self.graphics_provider_combo.append(
                '/run/host', 'Host system',
            )

        if env is None or env != '':
            self.graphics_provider_combo.append(
                '',
                "Container's own libraries (probably won't work)",
            )

        self.graphics_provider_combo.set_active(0)
        self.graphics_provider_combo.connect(
            'changed', self._something_changed_cb,
        )
        self.grid.attach(self.graphics_provider_combo, 1, row, 2, 1)
        row += 1

        label = Gtk.Label.new('Home directory')
        self.grid.attach(label, 0, row, 1, 1)

        self.share_home_combo = Gtk.ComboBoxText.new()
        self.share_home_combo.append(None, "Don't override")
        self.share_home_combo.append('1', 'Shared between all games')
        self.share_home_combo.append(
            '0',
            ('Separate per game '
             '(experimental, breaks Steam features)'),
        )
        self.share_home_combo.set_active(0)
        self.share_home_combo.connect(
            'changed', self._something_changed_cb,
        )
        self.grid.attach(self.share_home_combo, 1, row, 2, 1)
        row += 1

        label = Gtk.Label.new('Process ID namespace')
        self.grid.attach(label, 0, row, 1, 1)

        self.share_pid_combo = Gtk.ComboBoxText.new()
        self.share_pid_combo.append(None, "Don't override")
        self.share_pid_combo.append(
            '1',
            'Use the same process ID namespace as Steam',
        )
        self.share_pid_combo.append(
            '0',
            ('Create a new process ID namespace '
             '(experimental, breaks Steam features)'),
        )
        self.share_pid_combo.set_active(0)
        self.share_pid_combo.connect(
            'changed', self._something_changed_cb,
        )
        self.grid.attach(self.share_pid_combo, 1, row, 2, 1)
        row += 1

        label = Gtk.Label.new('Steam Overlay')
        self.grid.attach(label, 0, row, 1, 1)

        self.remove_game_overlay_combo = Gtk.ComboBoxText.new()
        self.remove_game_overlay_combo.append(None, "Don't override")
        self.remove_game_overlay_combo.append('0', 'Keep Steam Overlay')
        self.remove_game_overlay_combo.append(
            '1',
            'Remove Steam Overlay (breaks Steam features)',
        )
        self.remove_game_overlay_combo.set_active(0)
        self.remove_game_overlay_combo.connect(
            'changed', self._something_changed_cb,
        )
        self.grid.attach(self.remove_game_overlay_combo, 1, row, 2, 1)
        row += 1

        label = Gtk.Label.new('Vulkan layers')
        self.grid.attach(label, 0, row, 1, 1)

        self.vulkan_layers_combo = Gtk.ComboBoxText.new()
        self.vulkan_layers_combo.append(None, "Don't override")
        self.vulkan_layers_combo.append(
            '1',
            'Force importing Vulkan layers from host',
        )
        self.vulkan_layers_combo.append(
            '0',
            'Disable Vulkan layers from host',
        )
        self.vulkan_layers_combo.set_active(0)
        self.vulkan_layers_combo.connect(
            'changed', self._something_changed_cb,
        )
        self.grid.attach(self.vulkan_layers_combo, 1, row, 2, 1)
        row += 1

        label = Gtk.Label.new('Command injection')
        self.grid.attach(label, 0, row, 1, 1)

        self.launcher_service_combo = Gtk.ComboBoxText.new()
        self.launcher_service_combo.append(None, "Don't override")
        self.launcher_service_combo.append(
            'container-runtime', 'SteamLinuxRuntime_{soldier,sniper,...}',
        )
        self.launcher_service_combo.append(
            'proton', 'any Proton version',
        )
        self.launcher_service_combo.append(
            'scout-in-container', 'any layered scout-on-* runtime',
        )
        self.launcher_service_combo.append(
            '', 'None',
        )
        self.launcher_service_combo.set_active(0)
        self.launcher_service_combo.connect(
            'changed', self._something_changed_cb,
        )
        self.grid.attach(self.launcher_service_combo, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('Interactive terminal')
        self.grid.attach(label, 0, row, 1, 1)

        self.terminal_combo = Gtk.ComboBoxText.new()
        self.terminal_combo.append(None, "Don't override")
        self.terminal_combo.append('xterm', 'Run in an xterm')
        self.terminal_combo.append(
            'none',
            "Don't run in an interactive terminal",
        )
        self.terminal_combo.set_active(0)
        self.terminal_combo.connect(
            'changed', self._something_changed_cb,
        )
        self.grid.attach(self.terminal_combo, 1, row, 2, 1)
        row += 1

        label = Gtk.Label.new('Interactive shell')
        self.grid.attach(label, 0, row, 1, 1)

        self.shell_combo = Gtk.ComboBoxText.new()
        self.shell_combo.append(None, "Don't override")
        self.shell_combo.append('none', 'No, just run the command')
        self.shell_combo.append('after', 'After running the command')
        self.shell_combo.append('fail', 'If the command fails')
        self.shell_combo.append('instead', 'Instead of running the command')
        self.shell_combo.set_active(0)
        self.shell_combo.connect(
            'changed', self._something_changed_cb,
        )
        self.grid.attach(self.shell_combo, 1, row, 2, 1)

        row += 1

        self.debug_check = Gtk.CheckButton.new_with_label(
            'Extra debug logging',
        )
        self.debug_check.set_active(False)
        self.grid.attach(self.debug_check, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('Command to run')
        self.grid.attach(label, 0, row, 1, 1)

        self.command_entry = Gtk.Entry.new()
        self.command_entry.props.editable = True
        self.command_entry.set_text(to_shell(self.app.argv))
        self.command_entry.connect(
            'notify::text', self._command_entry_changed_cb,
        )
        self.grid.attach(self.command_entry, 1, row, 2, 1)

        row += 1

        label = Gtk.Label.new('Preview of final command')
        self.grid.attach(label, 0, row, 1, 1)

        self.final_command_view = Gtk.TextView.new()
        self.final_command_view.props.editable = False
        scrolled_window = Gtk.ScrolledWindow.new(None, None)
        scrolled_window.add(self.final_command_view)
        if hasattr(scrolled_window.props, 'propagate_natural_width'):
            scrolled_window.props.propagate_natural_width = True
            scrolled_window.props.propagate_natural_height = True
        else:
            scrolled_window.props.height_request = 120
        self.grid.attach(scrolled_window, 1, row, 2, 1)

        row += 1

        buttons_grid = Gtk.Grid(
            column_spacing=6,
            column_homogeneous=True,
            halign=Gtk.Align.END,
        )

        cancel_button = Gtk.Button.new_with_label('Cancel')
        cancel_button.connect('clicked', Gtk.main_quit)
        buttons_grid.attach(cancel_button, 0, 0, 1, 1)

        run_button = Gtk.Button.new_with_label('Run')
        run_button.connect('clicked', self.run_cb)
        buttons_grid.attach(run_button, 1, 0, 1, 1)

        self.vbox.pack_end(buttons_grid, False, False, 0)

        self._container_runtime_changed_id = (
            self.container_runtime_combo.connect(
                'changed',
                self._container_runtime_changed,
            )
        )

        self._pressure_vessel_changed_id = (
            self.pressure_vessel_combo.connect(
                'changed',
                self._pressure_vessel_changed,
            )
        )

        self._layered_runtime_changed_id = (
            self.layered_runtime_combo.connect(
                'changed',
                self._layered_runtime_changed,
            )
        )

        self._ldlp_runtime_changed_id = (
            self.ldlp_runtime_combo.connect(
                'changed',
                self._ldlp_runtime_changed,
            )
        )

        self._proton_changed_id = (
            self.proton_combo.connect(
                'changed',
                self._proton_changed,
            )
        )

    def parse_args(
        self,
        argv                            # type: typing.List[str]
    ):
        # type: (...) -> None
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '--compatible-with',
            choices=COMPAT_TARGETS + ['auto', 'any'],
            default='auto',
        )
        parser.add_argument(
            '--steam-runtime-env',
            action='append',
            default=[],
        )
        parser.add_argument('--verbose', action='store_true')
        parser.add_argument('command', nargs='+')
        args = parser.parse_args()

        for token in args.steam_runtime_env:
            if '=' not in token:
                parser.error('--steam-runtime-env requires VAR=VALUE argument')

            var, value = token.split('=', 1)
            self.steam_runtime_env[var] = value

        command_argv = args.command
        assert len(command_argv) >= 1

        self.app.runs_on = args.compatible_with

        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        if (
            len(command_argv) > 2
            and command_argv[0].endswith('ubuntu12_32/reaper')
            and '--' in command_argv[:-1]
        ):
            reaper_args = []        # type: typing.List[str]

            while len(command_argv) > 0:
                reaper_args.append(command_argv[0])
                command_argv = command_argv[1:]

                if reaper_args[-1] == '--':
                    break

            logger.debug('Detected reaper: %s', to_shell(reaper_args))
            logger.debug(
                'Remaining arguments: %s', to_shell(command_argv),
            )
            self.reaper = Reaper(
                path=command_argv[0],
                home=self.home,
                argv=reaper_args,
            )

        if (
            len(command_argv) > 2
            and command_argv[0].endswith('ubuntu12_32/steam-launch-wrapper')
            and '--' in command_argv[:-1]
        ):
            wrapper_args = []        # type: typing.List[str]

            while len(command_argv) > 0:
                wrapper_args.append(command_argv[0])
                command_argv = command_argv[1:]

                if wrapper_args[-1] == '--':
                    break

            logger.debug('Detected launch wrapper %s', to_shell(wrapper_args))
            logger.debug(
                'Remaining arguments: %s', to_shell(command_argv),
            )
            self.launch_wrapper = LaunchWrapper(
                path=command_argv[0],
                home=self.home,
                argv=wrapper_args,
            )

        for target in RUNTIMES:
            if (
                len(command_argv) > 2
                and command_argv[0].endswith((
                    '/SteamLinuxRuntime_%s/run' % target,
                    '/SteamLinuxRuntime_%s/run-in-%s' % (target, target),
                    '/SteamLinuxRuntime_%s/_v2-entry-point' % target,
                ))
                and '--' in command_argv[:-1]
            ):
                if args.compatible_with == 'auto':
                    self.app.runs_on = target

                runtime_args = []       # type: typing.List[str]

                while len(command_argv) > 0:
                    runtime_args.append(command_argv[0])
                    command_argv = command_argv[1:]

                    if runtime_args[-1] == '--':
                        break

                runtime = ContainerRuntimeDepot(
                    path=os.path.dirname(runtime_args[0]),
                    home=self.home,
                    argv=runtime_args,
                )
                runtime.provides = target
                self.default_container_runtime = runtime
                self.default_pressure_vessel = runtime.pressure_vessel

                logger.debug('Detected SLR: %s', to_shell(runtime_args))
                logger.debug(
                    'Remaining arguments: %s', to_shell(command_argv),
                )

        if (
            len(command_argv) > 2
            and command_argv[0].endswith(
                '/scout-on-soldier-entry-point-v2'
            )
            and '--' in command_argv[:-1]
        ):
            if args.compatible_with == 'auto':
                self.app.runs_on = 'scout'

            runtime_args = []

            while len(command_argv) > 0:
                runtime_args.append(command_argv[0])
                command_argv = command_argv[1:]

                if runtime_args[-1] == '--':
                    break

            self.default_layered_runtime = LayeredRuntime(
                path=os.path.dirname(runtime_args[0]),
                home=self.home,
                argv=runtime_args,
            )

            logger.debug('Detected layered SLR: %s', to_shell(runtime_args))
            logger.debug(
                'Remaining arguments: %s', to_shell(command_argv),
            )

        if (
            len(command_argv) > 2
            and command_argv[0].endswith('/proton')
            and command_argv[1] in ('run', 'waitforexitandrun')
        ):
            if args.compatible_with == 'auto':
                self.app.runs_on = 'windows'

            runtime_args = command_argv[:2]
            command_argv = command_argv[2:]

            if command_argv[0] == '--':
                runtime_args.append('--')
                command_argv = command_argv[1:]

            self.default_proton = Proton(
                path=os.path.dirname(runtime_args[0]),
                home=self.home,
                argv=runtime_args,
            )

            logger.debug('Detected Proton: %s', to_shell(runtime_args))
            logger.debug(
                'Remaining arguments: %s', to_shell(command_argv),
            )

        if 'PRESSURE_VESSEL_PREFIX' in os.environ:
            self.default_pressure_vessel = PressureVessel(
                os.environ['PRESSURE_VESSEL_PREFIX'],
                self.home,
            )

        if self.app.runs_on == 'auto':
            self.app.runs_on = 'scout'

        logger.debug('Assuming final app runs on: %s', self.app.runs_on)
        self.app.argv = command_argv
        self.command_entry.set_text(to_shell(command_argv))
        self.refresh_runtimes()

    def var_path_browse_cb(self, button):
        # type: (typing.Any) -> None

        dialog = Gtk.FileChooserDialog(
            title='Choose variable data directory',
            parent=self.window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            buttons=("Open", Gtk.ResponseType.ACCEPT),
        )

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.var_path_entry.set_text(dialog.get_filename())

        dialog.destroy()

    def _search(
        self,
        source_of_runtimes,             # type: str
        seen,                           # type: typing.Set[str]
        in_runtime=False                # type: bool
    ):
        # type: (...) -> None

        if not os.path.isdir(source_of_runtimes):
            return

        try:
            source_of_runtimes = os.path.realpath(source_of_runtimes)
        except OSError:
            return

        if source_of_runtimes in seen:
            return

        seen.add(source_of_runtimes)

        for member in os.listdir(source_of_runtimes):
            path = os.path.realpath(
                os.path.join(source_of_runtimes, member)
            )

            if member.startswith('SteamLinuxRuntime') and not in_runtime:
                if (
                    os.path.isdir(path)
                    and os.path.exists(os.path.join(path, 'run'))
                    and path not in self.container_runtimes
                ):
                    # Note that SteamLinuxRuntime (1070560) also has a
                    # _v2-entry-point, so we can't use that to detect
                    # complete container runtimes; but we should prefer
                    # to use it to run container runtimes, to be more like
                    # what Steam would do in the absence of this script.
                    exe = os.path.join(path, '_v2-entry-point')

                    if not os.path.exists(exe):
                        exe = os.path.join(path, 'run')

                    container_runtime = ContainerRuntimeDepot(
                        path=path,
                        home=self.home,
                        argv=[exe, '--'],
                    )
                    logger.debug(
                        'Discovered container runtime depot: %s', path,
                    )
                    logger.debug(
                        'Arguments: %s', to_shell(container_runtime.argv),
                    )
                    self.container_runtimes[path] = container_runtime
                    pv = container_runtime.pressure_vessel

                    if pv is not None:
                        logger.debug(
                            'Discovered pressure-vessel in %s: %s',
                            path, pv.path,
                        )

                        if pv.path not in self.pressure_vessels:
                            self.pressure_vessels[pv.path] = pv

                    self._search(path, seen, in_runtime=True)
                elif (
                    os.path.isdir(path)
                    and os.path.exists(
                        os.path.join(path, 'scout-on-soldier-entry-point-v2')
                    )
                    and path not in self.layered_runtimes
                ):
                    layered_runtime = LayeredRuntime(
                        path=path,
                        home=self.home,
                        argv=[
                            os.path.join(
                                path,
                                'scout-on-soldier-entry-point-v2',
                            ),
                            '--',
                        ],
                    )
                    logger.debug(
                        'Discovered layered runtime depot: %s', path,
                    )
                    logger.debug(
                        'Arguments: %s', to_shell(layered_runtime.argv),
                    )
                    self.layered_runtimes[path] = layered_runtime

                continue

            if member.startswith('Proton ') and not in_runtime:
                if (
                    os.path.isdir(path)
                    and os.path.exists(os.path.join(path, 'proton'))
                    and path not in self.proton_versions
                ):
                    proton = Proton(
                        path=path,
                        home=self.home,
                        argv=[
                            os.path.join(path, 'proton'), 'waitforexitandrun',
                        ],
                    )
                    logger.debug(
                        'Discovered Proton: %s', path,
                    )
                    logger.debug(
                        'Arguments: %s', to_shell(proton.argv),
                    )
                    self.proton_versions[path] = proton

                continue

            metadata = os.path.join(path, 'metadata')
            files = os.path.join(path, 'files')

            if os.path.isdir(files) and os.path.isfile(metadata):
                logger.debug(
                    'Discovered possible runtime directory: %s', path,
                )
                if path not in self.container_runtimes:
                    self.container_runtimes[path] = DirectoryRuntime(
                        path,
                        home=self.home,
                    )

                continue

            if member.endswith(('-runtime.tar.gz', '-sysroot.tar.gz')):
                # runtime and sysroot happen to be the same length!
                buildid_file = os.path.join(
                    source_of_runtimes,
                    member[:-len('-runtime.tar.gz')] + '-buildid.txt',
                )

                if os.path.exists(buildid_file):
                    logger.debug(
                        'Discovered possible archive runtime: %s', path,
                    )
                    if path not in self.container_runtimes:
                        self.container_runtimes[path] = ArchiveRuntime(
                            path,
                            buildid_file=buildid_file,
                            home=self.home,
                        )

                continue

            if member in ('steam-runtime', 'steam-runtime-heavy'):
                logger.debug(
                    'Discovered possible LD_LIBRARY_PATH runtime: %s', path,
                )

                if path not in self.container_runtimes:
                    self.ldlp_runtimes[path] = LdlpRuntime(
                        path,
                        home=self.home,
                    )

            if (
                member == 'pressure-vessel'
                and os.path.exists(
                    os.path.join(
                        path,
                        'bin',
                        'pressure-vessel-wrap',
                    )
                )
                and path not in self.pressure_vessels
            ):
                logger.debug(
                    'Discovered additional pressure-vessel version: %s',
                    path,
                )
                self.pressure_vessels[path] = PressureVessel(
                    path,
                    self.home,
                )

    @contextlib.contextmanager
    def _pause_changes(self):
        # type: (...) -> typing.Generator[Gui, None, None]
        try:
            self._changing += 1
            yield self
        finally:
            self._changing -= 1

        if self._changing:
            return

        if self._changing_container_runtime:
            self._changing_container_runtime = False
            widgets = [
                self.graphics_provider_combo,
                self.layered_runtime_combo,
                self.remove_game_overlay_combo,
                self.share_home_combo,
                self.share_pid_combo,
                self.vulkan_layers_combo,
            ]

            if (
                self.default_pressure_vessel is None
                and not self.pressure_vessels
            ):
                widgets.extend([
                    self.shell_combo,
                    self.terminal_combo,
                ])

            if self.container_runtime_combo.get_active_id() == '/':
                logger.debug('Selected absence of container runtime')

                for widget in widgets:
                    widget.set_sensitive(False)
            else:
                rt = self.container_runtimes.get(
                    self.container_runtime_combo.get_active_id()
                )
                assert rt
                logger.debug(
                    'Selected container runtime: %s %s (%r)',
                    rt.__class__.__name__, rt.path, rt.argv,
                )

                selected = self.pressure_vessel_combo.get_active_id()
                assert selected is not None
                assert selected
                assert selected != '/'

                if isinstance(rt, ContainerRuntimeDepot):
                    its_pv = rt.pressure_vessel
                    if its_pv is not None and selected != its_pv.path:
                        self.pressure_vessel_combo.set_active_id(its_pv.path)

                    self.var_path_entry.set_text(rt.var_path)
                else:
                    # keep the previous self.var_path_entry, it's better
                    # than nothing...
                    pass

                for widget in widgets:
                    widget.set_sensitive(True)

                # If soldier or sniper was selected, try to use a layered
                # runtime to provide a scout-compatible ABI.
                logger.debug(
                    'App runs on %s, runtime provides %s',
                    self.app.runs_on,
                    rt.provides,
                )
                if self.app.runs_on == 'scout' and rt.provides != 'scout':
                    layered_runtime = self.default_layered_runtime

                    if (
                        layered_runtime is not None
                        and layered_runtime.provides == 'scout'
                    ):
                        logger.debug(
                            'Using layered runtime %s',
                            layered_runtime.path,
                        )
                        self.layered_runtime_combo.set_active_id(
                            layered_runtime.path,
                        )

        self.build_argv()

    def refresh_runtimes(self):
        # type: (...) -> None
        with self._pause_changes():
            selected_container = self.container_runtime_combo.get_active_id()
            self.container_runtime_combo.remove_all()
            self.container_runtimes = {}
            container_runtime = self.default_container_runtime

            if container_runtime is None:
                self.container_runtime_combo.append('/', 'None')
            else:
                path = container_runtime.path
                self.container_runtimes[path] = container_runtime
                self.container_runtime_combo.append(
                    path, container_runtime.description,
                )

            selected_layered = self.layered_runtime_combo.get_active_id()
            self.layered_runtime_combo.remove_all()
            self.layered_runtimes = {}
            layered_runtime = self.default_layered_runtime

            if layered_runtime is None:
                self.layered_runtime_combo.append('/', 'None')
            else:
                self.layered_runtimes[layered_runtime.path] = layered_runtime
                self.layered_runtime_combo.append(
                    layered_runtime.path,
                    layered_runtime.description,
                )

            selected_ldlp = self.ldlp_runtime_combo.get_active_id()
            self.ldlp_runtime_combo.remove_all()
            self.ldlp_runtime_combo.append(None, "Don't override")

            selected_pv = self.pressure_vessel_combo.get_active_id()
            self.pressure_vessel_combo.remove_all()
            self.pressure_vessels = {}
            pressure_vessel = self.default_pressure_vessel

            if pressure_vessel is not None:
                self.pressure_vessels[pressure_vessel.path] = pressure_vessel
                self.pressure_vessel_combo.append(
                    pressure_vessel.path,
                    pressure_vessel.description,
                )

            selected_proton = self.proton_combo.get_active_id()
            self.proton_combo.remove_all()
            self.proton_versions = {}
            proton = self.default_proton

            if proton is None:
                self.proton_combo.append('/', 'None')
            else:
                self.proton_versions[proton.path] = proton
                self.proton_combo.append(
                    proton.path,
                    proton.description,
                )

            # Search for SteamLinuxRuntime, etc. in plausible Steam libraries
            search_path = []        # type: typing.List[typing.Optional[str]]
            seen = set()            # type: typing.Set[str]

            search_path.append(os.path.expanduser('~/.steam/root/ubuntu12_32'))
            search_path.append(os.path.expanduser('~/.steam/root/ubuntu12_64'))

            for path in os.getenv('STEAM_COMPAT_LIBRARY_PATHS', '').split(':'):
                if path:
                    search_path.append(
                        os.path.join(path, 'steamapps', 'common'),
                    )

            search_path.append(
                os.path.expanduser('~/.steam/steam/steamapps/common')
            )

            if 'XDG_DATA_HOME' in os.environ:
                search_path.append(
                    os.path.expanduser('$XDG_DATA_HOME/Steam/steamapps/common')
                )

            search_path.append(
                os.path.expanduser('~/.local/share/Steam/steamapps/common')
            )
            search_path.append(
                os.path.expanduser('~/SteamLibrary/steamapps/common')
            )
            search_path.append(os.path.expanduser('~/tmp'))
            search_path.append('.')

            search_path.append(os.getenv('PRESSURE_VESSEL_RUNTIME_BASE'))

            for search in search_path:
                if search is None:
                    continue

                source_of_runtimes = os.path.join(
                    os.path.dirname(__file__),
                    search,
                )

                if not os.path.isdir(source_of_runtimes):
                    continue

                self._search(source_of_runtimes, seen)

            already_had_default = (self.default_layered_runtime is not None)

            # Do these first, because they influence what's listed in the
            # container runtime chooser
            for path, layered_runtime in sorted(self.layered_runtimes.items()):
                assert layered_runtime is not None

                if layered_runtime != self.default_layered_runtime:
                    self.layered_runtime_combo.append(
                        path, layered_runtime.description,
                    )

                if self.default_layered_runtime is None:
                    self.default_layered_runtime = layered_runtime

            if already_had_default:
                self.layered_runtime_combo.append('/', 'None')

            if self.app.runs_on in RUNTIMES:
                list_first = self.app.runs_on
            elif self.default_container_runtime is not None:
                list_first = self.default_container_runtime.provides
            else:
                list_first = ''

            for path, runtime in sorted(
                self.container_runtimes.items(),
                key=lambda pair: pair[1].get_sort_weight(list_first),
            ):
                assert runtime is not None

                if (
                    runtime != self.default_container_runtime
                    and (
                        self.app.runs_on not in RUNTIMES
                        or not runtime.provides
                        or self.app.runs_on == runtime.provides
                        or (
                            self.app.runs_on == 'scout'
                            and self.default_layered_runtime is not None
                        )
                    )
                ):
                    self.container_runtime_combo.append(
                        path, runtime.description,
                    )

            for path, pressure_vessel in sorted(self.pressure_vessels.items()):
                assert pressure_vessel is not None

                if pressure_vessel != self.default_pressure_vessel:
                    self.pressure_vessel_combo.append(
                        path,
                        pressure_vessel.description,
                    )

            for path, ldlp_runtime in sorted(self.ldlp_runtimes.items()):
                assert ldlp_runtime is not None
                self.ldlp_runtime_combo.append(path, ldlp_runtime.description)

            for path, proton in sorted(self.proton_versions.items()):
                assert proton is not None

                if (
                    proton != self.default_proton
                    and self.app.runs_on == 'windows'
                ):
                    self.proton_combo.append(path, proton.description)

            if self.default_container_runtime is not None:
                self.container_runtime_combo.append('/', 'None')

            # There is no "none" option for pressure-vessel

            self.ldlp_runtime_combo.append('/', 'None')

            if (
                self.default_proton is not None
                and self.app.runs_on != 'windows'
            ):
                self.proton_combo.append('/', 'None')

            if (
                selected_container is not None
                and self.container_runtime_combo.set_active_id(
                    selected_container,
                )
            ):
                pass
            else:
                self.container_runtime_combo.set_active(0)

            if (
                selected_pv is not None
                and self.pressure_vessel_combo.set_active_id(selected_pv)
            ):
                pass
            else:
                self.pressure_vessel_combo.set_active(0)

            if (
                selected_layered is not None
                and self.layered_runtime_combo.set_active_id(selected_layered)
            ):
                pass
            else:
                self.layered_runtime_combo.set_active(0)

            if (
                selected_ldlp is not None
                and self.ldlp_runtime_combo.set_active_id(selected_ldlp)
            ):
                pass
            else:
                self.ldlp_runtime_combo.set_active(0)

            if (
                selected_proton is not None
                and self.proton_combo.set_active_id(selected_proton)
            ):
                pass
            else:
                self.proton_combo.set_active(0)

            self._container_runtime_changed(self.container_runtime_combo)

    def _container_runtime_changed(self, combo):
        # type: (typing.Any) -> None
        with self._pause_changes():
            logger.debug(
                'Selected container runtime: %s', combo.get_active_id(),
            )
            self._changing_container_runtime = True

    def _pressure_vessel_changed(self, combo):
        # type: (typing.Any) -> None
        with self._pause_changes():
            logger.debug(
                'Selected pressure-vessel: %s', combo.get_active_id(),
            )

    def _layered_runtime_changed(self, combo):
        # type: (typing.Any) -> None
        with self._pause_changes():
            container = self.container_runtime_combo.get_active_id()

            if combo.get_active_id() == '/':
                logger.debug('Selected absence of layered runtime')

                if container and container != '/':
                    self.ldlp_runtime_combo.set_sensitive(False)
                else:
                    self.ldlp_runtime_combo.set_sensitive(True)
            else:
                rt = self.layered_runtimes.get(combo.get_active_id())
                assert rt
                logger.debug(
                    'Selected layered runtime: %s %s (%r)',
                    rt.__class__.__name__, rt.path, rt.argv,
                )

                if container and container != '/':
                    self.ldlp_runtime_combo.set_sensitive(True)
                else:
                    self.ldlp_runtime_combo.set_sensitive(False)

    def _ldlp_runtime_changed(self, combo):
        # type: (typing.Any) -> None
        with self._pause_changes():
            if combo.get_active_id() == '/':
                logger.debug('Selected absence of LD_LIBRARY_PATH runtime')
            elif combo.get_active_id() is None:
                logger.debug(
                    'Selected automatic choice of LD_LIBRARY_PATH runtime',
                )
            else:
                rt = self.ldlp_runtimes.get(combo.get_active_id())
                assert rt
                logger.debug(
                    'Selected LD_LIBRARY_PATH runtime: %s %s (%r)',
                    rt.__class__.__name__, rt.path, rt.argv,
                )

    def _proton_changed(self, combo):
        # type: (typing.Any) -> None
        with self._pause_changes():
            logger.debug(
                'Selected Proton: %s', combo.get_active_id(),
            )

    def _something_changed_cb(self, sender='Something', *args, **kwargs):
        # type: (...) -> None
        with self._pause_changes():
            logger.debug('%s changed', sender)

    def _command_entry_changed_cb(self, entry, param_spec):
        # type: (typing.Any, typing.Any) -> None
        with self._pause_changes():
            logger.debug('Command to run changed to: %s', entry.props.text)
            argv = shlex.split(entry.props.text)
            logger.debug('Command parsed to %r', argv)
            self.app.argv = argv

    def run_cb(self, _ignored=None):
        # type: (typing.Any) -> None

        argv, environ = self.build_argv()
        try:
            os.execvpe(argv[0], argv, environ)
        except OSError:
            logger.error('Unable to run: %s', to_shell(argv))
            Gtk.main_quit()
            self.failed = True
            raise

    def build_argv(self):
        # type: (...) -> typing.Tuple[typing.List[str], typing.Dict[str, str]]

        lines = []                  # type: typing.List[str]
        argv = []                   # type: typing.List[str]

        environ = {}                # type: typing.Dict[str, str]

        components = []     # type: typing.List[Component]
        container = None    # type: typing.Optional[Component]
        component = None    # type: typing.Optional[Component]
        has_container_runtime = False
        inherit_ldlp_runtime = True

        reaper = self.reaper

        if reaper is not None:
            components.append(reaper)

        launch_wrapper = self.launch_wrapper

        if launch_wrapper is not None:
            components.append(launch_wrapper)

        selected = self.container_runtime_combo.get_active_id()

        if selected is None or not selected or selected == '/':
            container = None
        else:
            container = self.container_runtimes.get(selected)

        if container is not None:
            components.append(container)
            selected = self.layered_runtime_combo.get_active_id()

            if selected is None or not selected or selected == '/':
                component = None
            else:
                component = self.layered_runtimes.get(selected)

            if component is not None:
                components.append(component)
                component = None

                selected = self.ldlp_runtime_combo.get_active_id()

                if selected is None or not selected:
                    pass
                elif selected == '/':
                    # TODO: Shouldn't be allowed?
                    pass
                else:
                    component = self.ldlp_runtimes.get(selected)

                if component is not None:
                    environ['STEAM_RUNTIME_SCOUT'] = component.path
                    lines.append(to_shell([
                        'env', 'STEAM_RUNTIME_SCOUT={}'.format(component.path),
                    ]))
        else:
            selected = self.ldlp_runtime_combo.get_active_id()
            component = None

            if selected is None or not selected:
                pass
            elif selected == '/':
                inherit_ldlp_runtime = False
            else:
                component = self.ldlp_runtimes.get(selected)

            if component is not None:
                components.append(component)

        selected = self.proton_combo.get_active_id()

        if selected is None or not selected or selected == '/':
            component = None
        else:
            component = self.proton_versions.get(selected)

        if component is not None:
            components.append(component)

        if inherit_ldlp_runtime:
            environ.update(self.steam_runtime_env)

        for component in components:
            assert component is not None
            args = component.argv[:]

            if isinstance(component, ContainerRuntime):
                has_container_runtime = True
                selected = self.pressure_vessel_combo.get_active_id()
                assert selected is not None
                assert selected
                assert selected != '/'
                pv = self.pressure_vessels[selected]
                assert pv is not None

                if isinstance(component, ContainerRuntimeDepot):
                    its_pv = component.pressure_vessel
                    if (
                        its_pv is None
                        or pv.path != its_pv.path
                        or environ.get('PRESSURE_VESSEL_PREFIX') != pv.path
                    ):
                        environ['PRESSURE_VESSEL_PREFIX'] = pv.path
                else:
                    args = [
                        pv.unruntime,
                    ]

                    if isinstance(component, ArchiveRuntime):
                        args.append(
                            '--runtime-archive=' + component.path
                        )
                        args.append(
                            '--runtime-id=' + component.deploy_id
                        )
                    elif isinstance(component, DirectoryRuntime):
                        args.append('--runtime=' + component.path)
                    else:
                        raise AssertionError(
                            'Unhandled ContainerRuntime subclass: %r'
                            % component
                        )

                    args.append('--')

                value = self.graphics_provider_combo.get_active_id()

                if value is not None:
                    environ['PRESSURE_VESSEL_GRAPHICS_PROVIDER'] = value

                value = self.share_home_combo.get_active_id()

                if value is not None:
                    environ['PRESSURE_VESSEL_SHARE_HOME'] = value

                value = self.share_pid_combo.get_active_id()

                if value is not None:
                    environ['PRESSURE_VESSEL_SHARE_PID'] = value

                value = self.remove_game_overlay_combo.get_active_id()

                if value is not None:
                    environ['PRESSURE_VESSEL_REMOVE_GAME_OVERLAY'] = value

                value = self.vulkan_layers_combo.get_active_id()

                if value is not None:
                    environ['PRESSURE_VESSEL_IMPORT_VULKAN_LAYERS'] = value

                value = self.launcher_service_combo.get_active_id()

                if value is not None:
                    environ['STEAM_COMPAT_LAUNCHER_SERVICE'] = value

                value = self.terminal_combo.get_active_id()

                if value is not None:
                    environ['PRESSURE_VESSEL_TERMINAL'] = value

                value = self.shell_combo.get_active_id()

                if value is not None:
                    environ['PRESSURE_VESSEL_SHELL'] = value

                var_path = self.var_path_entry.get_text()

                if var_path:
                    os.makedirs(var_path, mode=0o755, exist_ok=True)
                    environ['PRESSURE_VESSEL_VARIABLE_DIR'] = var_path

            lines.append(to_shell(args))
            argv.extend(args)

        value = self.sdl_videodriver_combo.get_active_id()

        if value is not None:
            environ['SDL_VIDEODRIVER'] = value

        if self.debug_check.get_active():
            environ['STEAM_LINUX_RUNTIME_VERBOSE'] = '1'
            environ['G_MESSAGES_DEBUG'] = 'all'

        shell = self.shell_combo.get_active_id()
        terminal = self.terminal_combo.get_active_id()

        # If we're not using a container runtime, we can try to borrow the
        # pressure-vessel-adverb from any random copy of pressure-vessel
        # to get its "run in an xterm" code
        if (
            (shell is not None or terminal is not None)
            and not has_container_runtime
        ):
            any_pv = self.default_pressure_vessel

            if any_pv is None and self.pressure_vessels:
                any_pv = next(iter(sorted(self.pressure_vessels.items())))[1]

            if any_pv is not None:
                adverb = [any_pv.adverb]

                if shell is not None:
                    adverb.append('--shell=' + shell)

                if terminal is not None:
                    adverb.append('--terminal=' + terminal)

                adverb.append('--')
                argv.extend(adverb)
                lines.append(to_shell(adverb))

        argv.extend(self.app.argv)
        lines.append(to_shell(self.app.argv))

        env_lines = []                  # type: typing.List[str]

        for var, value in sorted(environ.items()):
            if value != os.environ.get(var):
                env_lines.append('{}={}'.format(var, to_shell([value])))

        lines = env_lines + lines

        self.final_command_view.get_buffer().set_text(
            ' \\\n'.join(lines), -1,
        )

        final_env = {}                  # type: typing.Dict[str, str]
        final_env.update(os.environ)
        final_env.update(environ)

        # The older pressure-vessel-test-ui would be redundant here,
        # so disable it.
        if 'PRESSURE_VESSEL_WRAP_GUI' in final_env:
            del final_env['PRESSURE_VESSEL_WRAP_GUI']

        return argv, final_env

    def run(self):
        # type: (...) -> None

        self.window.show_all()
        Gtk.main()

        if self.failed:
            sys.exit(126)


if __name__ == '__main__':
    logging.basicConfig()
    logging.getLogger().setLevel(logging.INFO)

    if '--check-gui-dependencies' in sys.argv:
        sys.exit(0)

    try:
        gui = Gui()
        gui.parse_args(sys.argv[1:])
        gui.run()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        logger.exception(str(e))
        sys.exit(125)
    except SystemExit:
        # Catch exit(2) from argparse.ArgumentParser.error, because we
        # want to reserve exit statuses < 125 for the launched tool
        sys.exit(125)
