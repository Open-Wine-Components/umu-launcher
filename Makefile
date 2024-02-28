PROJECT := ulwgl

BUILDDIR ?= build
DESTDIR ?=

PREFIX ?= /usr
BINDIR := $(PREFIX)/bin
LIBDIR := $(PREFIX)/lib
DATADIR := $(PREFIX)/share

.PHONY: all
all: reaper ulwgl ulwgl-launcher

ulwgl-run:
	$(info :: Building $@)
	sed 's|##INSTALL_PATH##|$(DATADIR)/$(PROJECT)|g' ULWGL/ulwgl-run.in > $(BUILDDIR)/$@

ulwgl-bin-install: ulwgl-run
	install -d $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 755 $(BUILDDIR)/$< $(DESTDIR)$(BINDIR)/ulwgl-run

ulwgl-dist-install:
	install -d $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_consts.py    -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_dl_util.py   -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_log.py       -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_plugins.py   -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_run.py     	 -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_util.py      -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ULWGL_VERSION.json -t $(DESTDIR)$(DATADIR)/$(PROJECT)

# Install both dist and sh script target
ulwgl-install: ulwgl-dist-install ulwgl-bin-install
# Install dist only target
#ulwgl-install: ulwgl-dist-install


ulwgl-launcher-run:
	$(info :: Building $@)
	sed 's|##INSTALL_PATH##|$(DATADIR)/$(PROJECT)|g' ULWGL/ULWGL-Launcher/ulwgl-run.in > $(BUILDDIR)/$@

ulwgl-launcher-bin-install: ulwgl-launcher-run
	install -d $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher
	install -Dm 755 $(BUILDDIR)/$< $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher/ulwgl-run

ulwgl-launcher-dist-install:
	install -d $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher
	install -Dm 644 ULWGL/ULWGL-Launcher/compatibilitytool.vdf -t $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher
	install -Dm 644 ULWGL/ULWGL-Launcher/toolmanifest.vdf      -t $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher

# Install both dist and sh script target
ulwgl-launcher-install: ulwgl-launcher-dist-install ulwgl-launcher-bin-install
# Install dist only target
#ulwgl-launcher-install: ulwgl-launcher-dist-install


reaper:
	$(info :: Building $@)
	meson setup $(BUILDDIR)/$@ subprojects/$@
	ninja -C $(BUILDDIR)/$@ -v

reaper-install: reaper
	install -Dm 755 $(BUILDDIR)/$</$< -t $(DESTDIR)$(DATADIR)/$(PROJECT)


clean:
	rm -rf $(BUILDDIR)

.PHONY: install-user
install-user:

.PHONY: install
install: reaper-install ulwgl-install ulwgl-launcher-install

