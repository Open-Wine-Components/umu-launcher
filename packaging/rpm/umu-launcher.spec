# Define the tag
%global tag %(git describe --abbrev=0 --tags)

# Define manual commit for tag
# This can be used to instead build from a manual commit.
%global manual_commit %(git rev-list -n 1 %{tag})

# Check if tag is defined and get the commit hash for the tag, otherwise use manual commit
%{!?tag: %global commit %{manual_commit}}
%{?tag: %global commit %(git rev-list -n 1 %{tag} 2>/dev/null || echo %{manual_commit})}

%global shortcommit %(c=%{commit}; echo ${c:0:7})

%global build_timestamp %(date +"%Y%m%d")

%global rel_build 1.%{build_timestamp}.%{shortcommit}%{?dist}

Name:           umu-launcher
Version:        %{tag}
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
BuildRequires:  cargo

# Can't use these yet, F41 doesn't ship urllib3 >= 2.0 needed
#BuildRequires:  python3-urllib3
#BuildRequires:  python3-pyzstd

Requires:	python
Requires:	python3
Requires:	python3-xlib
Requires:	python3-filelock

# Can't use these yet, F41 doesn't ship urllib3 >= 2.0 needed
#Requires:  python3-urllib3
#Requires:  python3-pyzstd

Recommends:	python3-cbor2
Recommends:	python3-xxhash
Recommends:	libzstd

# We need this for now to allow umu's builtin urllib3 version to be used.
# Can be removed when python3-urllib3 version is bumped >= 2.0
AutoReqProv: no


%description
%{name} A tool for launching non-steam games with proton

%prep
git clone https://github.com/Open-Wine-Components/umu-launcher.git
cd umu-launcher

if  %(git rev-list -n 1 %{tag}) == %{manual_commit}
 git checkout %{tag}
else
 git checkout %{manual_commit}
fi

git submodule update --init --recursive

%build
cd umu-launcher
# Update this when fedora ships urllib3 >= 2.0
#./configure.sh --prefix=/usr --use-system-pyzstd --use-system-urllib
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
