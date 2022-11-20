ifneq ($(shell which python3),)
PYTHON3 ?= python3
else
PYTHON3 ?= python
endif

all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	rm -rf work
	${PYTHON3} createexample.py

clean:
	rm -rf html work __pycache__ dokuforge/__pycache__
	rm -f *.pyc *~ dokuforge/*.pyc .coverage dokuforge/versioninfo.py

check: test

test: test.py
	${PYTHON3} test.py

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON3} -m coverage -x test.py
coverage: .coverage
	${PYTHON3} -m coverage -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
