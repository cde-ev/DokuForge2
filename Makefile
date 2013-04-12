ifneq ($(shell which python-coverage),)
PYTHON_COVERAGE ?= python-coverage
else
PYTHON_COVERAGE ?= coverage
endif

ifneq ($(shell which python2),)
PYTHON2 ?= python2
else
PYTHON2 ?= python
endif

all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	rm -rf work
	${PYTHON2} createexample.py

clean:
	rm -rf html work
	rm -f *.pyc *~ dokuforge/*.pyc .coverage

check: test

test: test.py
	${PYTHON2} test.py

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON_COVERAGE} -x test.py
coverage: .coverage
	${PYTHON_COVERAGE} -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
