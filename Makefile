
all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	python createexample.py

clean:
	rm -rf html work df
	rm -f *.pyc *~

.PHONY: all doc
