
all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	rm -rf work df
	python createexample.py

clean:
	rm -rf html work df
	rm -f *.pyc *~

check: test

test: test.py
	python test.py

.PHONY: all doc clean setup test check
