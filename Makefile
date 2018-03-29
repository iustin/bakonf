NAME=bakonf
VERSION=0.6.0
DISTDIR=$(NAME)-$(VERSION)

DOCS = \
	docs/bakonf.8

all: $(DOCS) site

.PHONY: maintainer-clean
maintainer-clean:
	rm -rf $(DOCS) site/

.PHONY: site
site:
	mkdocs build --strict

%.8: %.md
	pandoc -s -t man $< > $@

install:
	install -d -m 0700 $(DESTDIR)/etc/bakonf
	install -d -m 0700 $(DESTDIR)/etc/bakonf/sources
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf/archives
	install -D -m 0700 bakonf $(DESTDIR)/usr/bin/bakonf
	install -D -m 0600 bakonf.yml $(DESTDIR)/etc/bakonf/bakonf.yml
	install -m 0600 sources/*.yml $(DESTDIR)/etc/bakonf/sources
	install -D -m 0644 README $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)/README
	cp -a doc/* $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)
	install -D -m 0644 bakonf.8 $(DESTDIR)/usr/share/man/man8/bakonf.8
	install -D -m 0600 bakonf.cron $(DESTDIR)/etc/cron.d/bakonf

dist: lint $(DOCS)
	mkdir $(DISTDIR)
	cp bakonf.py $(DISTDIR)/bakonf
	cp bakonf.yml bakonf.cron $(DISTDIR)
	cp Makefile bakonf.spec $(DISTDIR)
	mkdir $(DISTDIR)/docs
	cp -a docs/usermanual.* $(DISTDIR)/docs/
	cp -a docs/bakonf.* $(DISTDIR)
	mkdir $(DISTDIR)/sources
	cp -a sources/*.yml $(DISTDIR)/sources
	cp README.md NEWS.md COPYING $(DISTDIR)
	tar cvzf $(NAME)-$(VERSION).tar.gz $(DISTDIR)
	rm -rf $(DISTDIR)

.PHONY: lint
lint:
	pep8 bakonf.py
	pylint bakonf.py

.PHONY: coverage
coverage:
	pytest-3 --cov=bakonf --cov-branch --cov-report=html

rpm:
	rpmbuild -ta $(NAME)-$(VERSION).tar.gz
