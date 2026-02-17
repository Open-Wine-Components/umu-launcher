# Tag is auto-inserted by workflow
%global tag 1.3.0

# Manual commit is auto-inserted by workflow
%global commit 24cdc86a1565764655c9de12404b2c5d12dec6e7

%global shortcommit %(c=%{commit}; echo ${c:0:7})

%global build_timestamp %(date +"%Y%m%d")

%global rel_build 1.%{build_timestamp}.%{shortcommit}%{?dist}

%if 0%{?fedora} <= 42
# F41 doesn't ship urllib3 >= 2.0 needed
%global urllib3 2.3.0
%endif

Name:           umu-launcher
Version:        %{tag}
Release:        %{rel_build}
Summary:        A tool for launching non-steam games with proton

License:        GPLv3
URL:            https://github.com/Open-Wine-Components/umu-launcher
Source0:        %{url}/archive/refs/tags/%{tag}.tar.gz#/%{name}-%{tag}.tar.gz

%if 0%{?fedora} <= 42
Source1:        https://github.com/urllib3/urllib3/releases/download/%{urllib3}/urllib3-%{urllib3}.tar.gz
%endif

BuildArch: %{_arch}
BuildRequires:  rpm-build
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
BuildRequires:  cargo
BuildRequires:  python3-hatch-vcs
BuildRequires:  python3-wheel
BuildRequires:  libzstd-devel
BuildRequires:  python3-pyzstd
BuildRequires:  python3-xlib
BuildRequires:  wget

%if 0%{?fedora} > 42
BuildRequires:  python3-urllib3
%endif

Requires:	python
Requires:	python3
Requires:	python3-xlib
Requires:	python3-pyzstd

%if 0%{?fedora} > 42
Requires:  python3-urllib3
%endif

Recommends:	python3-cbor2
Recommends:	python3-xxhash
Recommends:	libzstd

%if 0%{?fedora} <= 42
AutoReqProv: no
%endif

%description
%{name} A tool for launching non-steam games with proton

%prep
%autosetup -p 1
%if 0%{?fedora} <= 42
if ! find subprojects/urllib3/ -mindepth 1 -maxdepth 1 | read; then
    # Directory is empty, perform action
    mv %{SOURCE1} .
    tar -xf urllib3-%{urllib3}.tar.gz
    rm *.tar.gz
    mv urllib3-%{urllib3}/* subprojects/urllib3/
fi
%endif

%build

%if 0%{?fedora} <= 42
./configure.sh --prefix=/usr --use-system-pyzstd
%else
./configure.sh --prefix=/usr --use-system-pyzstd --use-system-urllib
%endif

make

%install
make DESTDIR=%{buildroot} PYTHONDIR=%{python3_sitelib} install

%files
%{_bindir}/umu-run
%{_datadir}/man/*
%{python3_sitelib}/umu*

%changelog
