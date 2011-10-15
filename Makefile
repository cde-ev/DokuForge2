
all: doc

doc:
	epydoc --config epydoc.conf

clean:
	rm -rf html
	rm -f *.pyc *~

.PHONY: all doc
