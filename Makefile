ifneq ($(shell which python3),)
PYTHON ?= python3
else
PYTHON ?= python
endif

all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	rm -rf work
	${PYTHON} createexample.py

clean:
	rm -rf html work
	rm -f *.pyc *~ dokuforge/*.pyc .coverage

check: test

test: test.py
	${PYTHON} test.py

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON} -m coverage -x test.py
coverage: .coverage
	${PYTHON} -m coverage -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
