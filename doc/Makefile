all: usermanual.pdf usermanual.html usermanual.txt bakonf.8

usermanual.html: usermanual.sgml
	db2html -u -o . usermanual.sgml
	rmdir usermanual || true

man.html:
	db2html bakonf.sgml

%.8: %.sgml
	docbook2man $^
	rm -f manpage.links manpage.refs

%.txt: %.sgml
	docbook2txt $^

%.pdf: %.sgml
	db2pdf $^
