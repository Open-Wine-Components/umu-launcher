# some macros useful for packaging python packages

# to include it unconditionally:
# include /usr/share/python3/python.mk
#
# to include it conditionally, and have the packaging working with earlier releases
# and backports:
# -include /usr/share/python/python.mk
# ifeq (,$(py_sitename))
#   py_sitename = site-packages
#   py_libdir = /usr/lib/python$(subst python,,$(1))/site-packages
#   py_sitename_sh = $(py_sitename)
#   py_libdir_sh = $(py_libdir)
# endif

# py_sitename: name of the site-packages/dist-packages directory depending
# on the python version. Call as: $(call py_sitename, <python version>).
# Don't use this in shell snippets inside loops.

py_sitename = $(if $(filter $(subst python,,$(1)), 2.3 2.4 2.5),site,dist)-packages

# py_libdir: absolute path to the default python library for third party
# stuff. Call as: $(call py_libdir, <python version>).
# Don't use this in shell snippets inside loops.

py_libdir = /usr/lib/python$(strip $(if $(findstring 3.,$(subst python,,$(1))),3,$(subst python,,$(1))))/$(py_sitename)

# py_pkgname: package name corresponding to the python version.
# Call as: $(call py_pkgname, <path>, <python version>).

py_pkgname = $(if $(findstring 3.,$(2)),$(subst python-,python3-,$(1)),$(1))

# distutils' build directory
py_builddir = $(shell python$(strip $(subst python,,$(1))) -c 'from distutils.command.build import build; from distutils.core import Distribution; b = build(Distribution()); b.finalize_options(); print(b.build_platlib)')


# The same macros for use inside loops in shell snippets

py_sitename_sh = $$(basename $$(_py_=$(strip $(1)); python$${_py_\#python*} -c 'from distutils import sysconfig; print(sysconfig.get_python_lib())'))

py_libdir_sh = $$(_py_=$(strip $(1)); python$${_py_\#python*} -c 'from distutils import sysconfig; print(sysconfig.get_python_lib())')

py_builddir_sh = $$(_py_=$(strip $(1)); python$${_py_\#python*} -c 'from distutils.command.build import build; from distutils.core import Distribution; b = build(Distribution()); b.finalize_options(); print(b.build_platlib)')

# Arguments to pass to setup.py install
py_setup_install_args = --install-layout=deb
