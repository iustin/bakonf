txt: usermanual.txt
html: usermanual.html

%.txt: %.sgml
	linuxdoc -B txt $^

%.html: %.sgml
	sgml2html -s 0 $^
