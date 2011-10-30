
all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	rm -rf work df
	python createexample.py

clean:
	rm -rf html work df
	rm -f *.pyc *~ dokuforge/*.pyc .coverage

check: test

test: test.py
	python test.py

.coverage:
	python-coverage -x test.py
coverage:.coverage
	python-coverage -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
