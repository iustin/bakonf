NAME=bakonf
VERSION=0.5.1
DISTDIR=$(NAME)-$(VERSION)
install:
	install -d -m 0700 $(DESTDIR)/etc/bakonf
	install -d -m 0700 $(DESTDIR)/etc/bakonf/sources
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf
	install -d -m 0700 $(DESTDIR)/var/lib/bakonf/archives
	install -D -m 0700 bakonf $(DESTDIR)/usr/sbin/bakonf
	install -D -m 0600 bakonf.xml $(DESTDIR)/etc/bakonf/bakonf.xml
	install -m 0600 sources/*.xml $(DESTDIR)/etc/bakonf/sources
	install -D -m 0644 README $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)/README
	cp -a doc/* $(DESTDIR)/usr/share/doc/$(NAME)-$(VERSION)
	install -D -m 0644 bakonf.8 $(DESTDIR)/usr/share/man/man8/bakonf.8
	install -D -m 0600 bakonf.cron $(DESTDIR)/etc/cron.d/bakonf

dist:
	mkdir $(DISTDIR)
	cp bakonf.py $(DISTDIR)/bakonf
	cp bakonf.xml bakonf.cron $(DISTDIR)
	cp Makefile bakonf.spec $(DISTDIR)
	make -C doc html usermanual.txt bakonf.8
	mkdir $(DISTDIR)/doc
	cp -a doc/usermanual $(DISTDIR)/doc/usermanual
	cp -a doc/usermanual.txt $(DISTDIR)/doc
	cp -a doc/bakonf.8 $(DISTDIR)
	mkdir $(DISTDIR)/sources
	cp -a sources/*.xml $(DISTDIR)/sources
	cp README COPYING $(DISTDIR)
	test -f ChangeLog && cp ChangeLog $(DISTDIR)
	tar cvzf $(NAME)-$(VERSION).tar.gz $(DISTDIR)
	rm -rf $(DISTDIR)

rpm:
	rpmbuild -ta $(NAME)-$(VERSION).tar.gz

changelog:
	rm ChangeLog || true
	rcs2log -u 'iusty	Iustin Pop	iusty@k1024.org' > ChangeLog
