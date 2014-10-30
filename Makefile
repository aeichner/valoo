all: xmlparser

xmlparser: xmlparser.c
	gcc -o xmlparser `xml2-config --cflags` `xml2-config --libs` xmlparser.c
