# Tag is auto-inserted by workflow
%global tag 1.2.5

# Manual commit is auto-inserted by workflow
%global commit a11540cbf2221a5671c4ced97c0bf7e61c98d21e

%global shortcommit %(c=%{commit}; echo ${c:0:7})

%global build_timestamp %(date +"%Y%m%d")

%global rel_build 1.%{build_timestamp}.%{shortcommit}%{?dist}

Name:           umu-launcher
Version:        %{tag}
Release:        %{rel_build}
Summary:        A tool for launching non-steam games with proton

License:        GPLv3
URL:            https://github.com/Open-Wine-Components/umu-launcher
Source0:        %{url}/archive/refs/tags/%{tag}.tar.gz#/%{name}-%{tag}.tar.gz

BuildArch:  x86_64
BuildRequires:  meson >= 0.54.0
BuildRequires:  ninja-build
BuildRequires:  cmake
BuildRequires:  g++
BuildRequires:  gcc-c++
BuildRequires:  scdoc
BuildRequires:  git
BuildRequires:  python3-devel
BuildRequires:  python3-build
BuildRequires:  python3-installer
BuildRequires:  python3-hatchling
BuildRequires:  python
BuildRequires:  python3
BuildRequires:  python3-pip
BuildRequires:  libzstd-devel
BuildRequires:  python3-hatch-vcs
BuildRequires:  python3-wheel
BuildRequires:  python3-xlib
BuildRequires:  python3-pyzstd
BuildRequires:  cargo

BuildRequires:  python3-urllib3

Requires:	python
Requires:	python3
Requires:	python3-xlib
Requires:	python3-pyzstd

Requires:  python3-urllib3

Recommends:	python3-cbor2
Recommends:	python3-xxhash
Recommends:	libzstd

%description
%{name} A tool for launching non-steam games with proton

%build
./configure.sh --prefix=/usr --use-system-pyzstd --use-system-urllib
make

%install
make DESTDIR=%{buildroot} PYTHONDIR=%{python3_sitelib} install

%files
%{_bindir}/umu-run
%{_datadir}/man/*
%{python3_sitelib}/umu*

%changelog
