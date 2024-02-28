PROJECT := ulwgl

OBJDIR ?= build
DESTDIR ?=

PREFIX ?= /usr
BINDIR := $(PREFIX)/bin
LIBDIR := $(PREFIX)/lib
DATADIR := $(PREFIX)/share

.PHONY: all
all: reaper ulwgl ulwgl-launcher


$(OBJDIR)/.build-ulwgl: | $(OBJDIR)
	$(info :: Building ulwgl )
	sed 's|##INSTALL_PATH##|$(DATADIR)/$(PROJECT)|g' ULWGL/ulwgl-run.in > $(OBJDIR)/ulwgl-run
	touch $(@)

ulwgl: $(OBJDIR)/.build-ulwgl

ulwgl-bin-install: ulwgl
	install -d $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 755 $(OBJDIR)/$(<)-run $(DESTDIR)$(BINDIR)/ulwgl-run

ulwgl-dist-install:
	$(info :: Installing ulwgl )
	install -d $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_consts.py    -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_dl_util.py   -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_log.py       -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_plugins.py   -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 755 ULWGL/ulwgl_run.py     	 -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ulwgl_util.py      -t $(DESTDIR)$(DATADIR)/$(PROJECT)
	install -Dm 644 ULWGL/ULWGL_VERSION.json -t $(DESTDIR)$(DATADIR)/$(PROJECT)

# Install both dist and sh script target
ulwgl-install: ulwgl-dist-install ulwgl-bin-install
# Install dist only target
#ulwgl-install: ulwgl-dist-install


$(OBJDIR)/.build-ulwgl-launcher: | $(OBJDIR)
	$(info :: Building ulwgl-launcher )
	sed 's|##INSTALL_PATH##|$(DATADIR)/$(PROJECT)|g' ULWGL/ULWGL-Launcher/ulwgl-run.in > $(OBJDIR)/ulwgl-launcher-run
	touch $(@)

ulwgl-launcher: $(OBJDIR)/.build-ulwgl-launcher

ulwgl-launcher-bin-install: ulwgl-launcher
	install -d $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher
	install -Dm 755 $(OBJDIR)/$(<)-run $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher/ulwgl-run

ulwgl-launcher-dist-install:
	$(info :: Installing ulwgl-launcher )
	install -d $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher
	install -Dm 644 ULWGL/ULWGL-Launcher/compatibilitytool.vdf -t $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher
	install -Dm 644 ULWGL/ULWGL-Launcher/toolmanifest.vdf      -t $(DESTDIR)$(DATADIR)/$(PROJECT)/ULWGL-Launcher

# Install both dist and sh script target
ulwgl-launcher-install: ulwgl-launcher-dist-install ulwgl-launcher-bin-install
# Install dist only target
#ulwgl-launcher-install: ulwgl-launcher-dist-install


$(OBJDIR)/.build-reaper: | $(OBJDIR)
	$(info :: Building reaper )
	meson setup $(OBJDIR)/reaper subprojects/reaper
	ninja -C $(OBJDIR)/reaper -v
	touch $(@)

reaper: $(OBJDIR)/.build-reaper

reaper-install: reaper
	$(info :: Installing reaper )
	install -Dm 755 $(OBJDIR)/$</$< -t $(DESTDIR)$(DATADIR)/$(PROJECT)


.PHONY: $(OBJDIR)
$(OBJDIR):
	@mkdir -p $(OBJDIR)


clean:
	rm -rf $(OBJDIR)

.PHONY: install-user
install-user:

.PHONY: install
install: reaper-install ulwgl-install ulwgl-launcher-install

