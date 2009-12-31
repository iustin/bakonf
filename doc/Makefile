all: usermanual.html bakonf.8

%.html: %.rst
	rst2html $< > $@

man.html:
	db2html bakonf.sgml

%.8: %.sgml
	docbook2man $^
	rm -f manpage.links manpage.refs
