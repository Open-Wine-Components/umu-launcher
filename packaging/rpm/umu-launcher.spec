# Define the manual commit as a fallback
%define manual_commit e9cb4d764013d4c8c3d1166f59581da8f56a3d83

# Optionally define the tag
# Check if tag is defined and get the commit hash for the tag, otherwise use manual commit
%{!?tag: %global commit %{manual_commit}}
%{?tag: %global commit %(git rev-list -n 1 %{tag} 2>/dev/null || echo %{manual_commit})}

%global shortcommit %(c=%{commit}; echo ${c:0:7})

%global build_timestamp %(date +"%Y%m%d")

%global rel_build 1.%{build_timestamp}.%{shortcommit}%{?dist}

Name:           umu-launcher
Version:        1.1.4
Release:        %{rel_build}
Summary:        A tool for launching non-steam games with proton

License:        GPLv3
URL:            https://github.com/Open-Wine-Components/umu-launcher

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

Requires:	python
Requires:	python3
Requires:	python3-xlib

Recommends:	python3-cbor2
Recommends:	python3-xxhash
Recommends:	libzstd


%description
%{name} A tool for launching non-steam games with proton

%prep
git clone --single-branch --branch main https://github.com/Open-Wine-Components/umu-launcher.git
cd umu-launcher
git submodule update --init --recursive

%build
cd umu-launcher
./configure.sh --prefix=/usr
make

%install
cd umu-launcher
make DESTDIR=%{buildroot} PYTHONDIR=%{python3_sitelib} install

%files
%{_bindir}/umu-run
%{_datadir}/man/*
%{_datadir}/steam/compatibilitytools.d/umu-launcher/
%{python3_sitelib}/umu*

%changelog
