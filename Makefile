NAME=bakonf
VERSION=0.3
DISTDIR=$(NAME)-$(VERSION)
install:
	install -d -m 0700 $(DESTDIR)/etc/bakonf
	install -d -m 0700 $(DESTDIR)/etc/bakonf/sources
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf/work
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf/archives
	install -D -m 0700 bakonf.py $(DESTDIR)/usr/sbin/bakonf.py
	install -D -m 0600 bakonf.conf $(DESTDIR)/etc/bakonf/bakonf.conf
	install -m 0600 sources/*.sources $(DESTDIR)/etc/bakonf/sources
	install -D -m 0644 README $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)/README

dist:
	dir
	mkdir $(DISTDIR)
	cp bakonf.py bakonf.conf $(DISTDIR)
	cp Makefile bakonf.spec $(DISTDIR)
	cp -a doc $(DISTDIR)
	cp -a sources $(DISTDIR)
	cp README COPYING $(DISTDIR)
	test -f ChangeLog && cp ChangeLog $(DISTDIR)
	tar cvzf $(NAME)-$(VERSION).tar.gz $(DISTDIR)
	rm -rf $(DISTDIR)

rpm:
	rpm -ta $(NAME)-$(VERSION).tar.gz

changelog:
	rm ChangeLog || true
	rcs2log -u 'iusty	Iustin Pop	iusty@yahoo.com' > ChangeLog
