NAME=bakonf
VERSION=0.2
DISTDIR=$(NAME)-$(VERSION)
install:
	install -D -m 0700 bakonf $(DESTDIR)/usr/sbin/bakonf
	install -D -m 0700 bakonf_scanner.py $(DESTDIR)/usr/libexec/bakonf/bakonf_scanner.py
	install -D -m 0600 bakonf_scanner.cfg $(DESTDIR)/etc/bakonf/bakonf_scanner.cfg
	install -D -m 0644 README $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)/README

dist:
	dir
	mkdir $(DISTDIR)
	cp bakonf $(DISTDIR)
	cp bakonf_scanner.py bakonf_scanner.cfg $(DISTDIR)
	cp Makefile bakonf.spec $(DISTDIR)
	cp -a doc $(DISTDIR)
	cp README COPYING $(DISTDIR)
	tar cvzf $(NAME)-$(VERSION).tar.gz $(DISTDIR)
	rm -rf $(DISTDIR)

rpm:
	rpm -ta $(NAME)-$(VERSION).tar.gz
