NAME=bakonf
VERSION=0.6.0
DISTDIR=$(NAME)-$(VERSION)

DOCS = \
	doc/usermanual.html \
	doc/bakonf.8

all: $(DOCS)

.PHONY: maintainer-clean
maintainer-clean:
	rm -f $(DOCS)

%.html: %.txt
	rst2html $< > $@

%.8: %.md
	pandoc -s -t man $< > $@

doc/man.html:
	db2html doc/bakonf.sgml

install:
	install -d -m 0700 $(DESTDIR)/etc/bakonf
	install -d -m 0700 $(DESTDIR)/etc/bakonf/sources
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf/archives
	install -D -m 0700 bakonf $(DESTDIR)/usr/bin/bakonf
	install -D -m 0600 bakonf.xml $(DESTDIR)/etc/bakonf/bakonf.xml
	install -m 0600 sources/*.xml $(DESTDIR)/etc/bakonf/sources
	install -D -m 0644 README $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)/README
	cp -a doc/* $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)
	install -D -m 0644 bakonf.8 $(DESTDIR)/usr/share/man/man8/bakonf.8
	install -D -m 0600 bakonf.cron $(DESTDIR)/etc/cron.d/bakonf

dist: lint $(DOC)
	mkdir $(DISTDIR)
	cp bakonf.py $(DISTDIR)/bakonf
	cp bakonf.xml bakonf.cron $(DISTDIR)
	cp Makefile bakonf.spec $(DISTDIR)
	mkdir $(DISTDIR)/doc
	cp -a doc/usermanual.* $(DISTDIR)/doc/
	cp -a doc/bakonf.* $(DISTDIR)
	mkdir $(DISTDIR)/sources
	cp -a sources/*.xml $(DISTDIR)/sources
	cp README NEWS COPYING $(DISTDIR)
	tar cvzf $(NAME)-$(VERSION).tar.gz $(DISTDIR)
	rm -rf $(DISTDIR)

.PHONY: lint
lint:
	pep8 bakonf.py
	pylint bakonf.py

rpm:
	rpmbuild -ta $(NAME)-$(VERSION).tar.gz
