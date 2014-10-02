
all: trunnel-manual.html

trunnel-manual.html: trunnel.md
	markdown trunnel.md > trunnel-manual.html.tmp && mv trunnel-manual.html.tmp trunnel-manual.html

clean:
	rm -f trunnel-manual.html trunnel-manual.html.tmp
