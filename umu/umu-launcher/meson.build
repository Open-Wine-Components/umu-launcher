fs = import('fs')

umu_run_launcher_cfg = configuration_data()
if get_option('flatpak')
    umu_run_launcher_cfg.set('INSTALL_PATH', 'org.openwinecomponents.umu.launcher')
else
    umu_run_launcher_cfg.set('INSTALL_PATH', umu_run_cfg.get('INSTALL_PATH'))
endif

configure_file(
    input : 'umu-run.in',
    output : 'umu-run',
    configuration : umu_run_launcher_cfg,
    install : true,
    install_dir : umu_install_path / fs.name(meson.current_source_dir()),
    install_mode: 'rwxr-xr-x',
)

install_data(
    [
        'compatibilitytool.vdf',
        'toolmanifest.vdf'
    ],
    install_dir: umu_install_path / fs.name(meson.current_source_dir()),
)
