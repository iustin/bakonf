all: usermanual.ps html usermanual.txt bakonf.8

html: usermanual.sgml
	db2html usermanual.sgml

man.html:
	db2html bakonf.sgml

%.8: %.sgml
	docbook2man $^

%.txt: %.sgml
	docbook2txt $^

%.ps: %.sgml
	db2ps $^
