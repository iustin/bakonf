NAME=bakonf
VERSION=0.7.0
DISTDIR=$(NAME)-$(VERSION)

DOCS = \
	docs/bakonf.8

PY_FILES = bakonf.py tests/test_bakonf.py

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
	install -D -m 0700 bakonf.py $(DESTDIR)/usr/bin/bakonf
	install -D -m 0600 bakonf.yml $(DESTDIR)/etc/bakonf/bakonf.yml
	install -m 0600 sources/*.yml $(DESTDIR)/etc/bakonf/sources
	install -d -m 0755 $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)
	install -m 0644 README.md NEWS.md docs/usermanual.md \
		$(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)/
	install -D -m 0644 docs/bakonf.8 $(DESTDIR)/usr/share/man/man8/bakonf.8
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
	pycodestyle $(PY_FILES)
	pylint $(PY_FILES)

.PHONY: coverage
coverage:
	PYTHONPATH=. python3 -m pytest --cov=bakonf --cov-branch --cov-report=html tests/

.PHONY: test
test:
	PYTHONPATH=. pytest-3 tests/

.PHONY: check
check: test mypy lint

.PHONY: ci
ci:
	while inotifywait -e CLOSE_WRITE bakonf.py tests/test_bakonf.py; do make -k check; done

.PHONY: mypy
mypy:
	mypy --config-file mypy.ini bakonf.py

rpm:
	rpmbuild -ta $(NAME)-$(VERSION).tar.gz
