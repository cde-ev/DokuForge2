ifneq ($(shell which python-coverage),)
PYTHON_COVERAGE ?= python-coverage
else
PYTHON_COVERAGE ?= coverage
endif

all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	rm -rf work
	python createexample.py

clean:
	rm -rf html work
	rm -f *.pyc *~ dokuforge/*.pyc .coverage

check: test

test: test.py
	python test.py
	python testparser.py

.coverage:
	${PYTHON_COVERAGE} run test.py
coverage: .coverage
	${PYTHON_COVERAGE} report -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
