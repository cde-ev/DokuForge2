
all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	python createuserdb.py

clean:
	rm -rf html work
	rm -f *.pyc *~

.PHONY: all doc
