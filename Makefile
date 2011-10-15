
all: doc

doc:
	epydoc *.py

clean:
	rm -rf html
	rm -f *.pyc *~

.PHONY: all doc
