ifneq ($(shell which python2),)
PYTHON2 ?= python2
else
PYTHON2 ?= python
endif
PYTHON3 ?= python3

all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	rm -rf work
	${PYTHON2} createexample.py

clean:
	rm -rf html work __pycache__ dokuforge/__pycache__
	rm -f *.pyc *~ dokuforge/*.pyc .coverage dokuforge/versioninfo.py

check: test

test:test2 test3
test2: test.py
	${PYTHON2} test.py
test3: test.py
	${PYTHON3} test.py

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON2} -m coverage -x test.py
coverage: .coverage
	${PYTHON2} -m coverage -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
