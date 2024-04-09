project('umu',
    ['cpp'],
    license :  'GPL-3.0-only',
    license_files : ['LICENSE'],
)

# 'libdir' is likely a more conformant target directory than 'datadir'
umu_install_path = get_option('datadir') / meson.project_name()

subproject('reaper',
    default_options : [
        'prefix=' + get_option('prefix'),
        'bindir=' + get_option('prefix') / umu_install_path,
    ],
)

subdir('umu')
if not get_option('flatpak')
    subdir('docs')
endif
