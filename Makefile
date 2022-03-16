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
	rm -rf html work
	rm -f *.pyc *~ dokuforge/*.pyc .coverage

check: test

test: test.py
	${PYTHON3} test.py

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON3} -m coverage run --include=dokuforge/*.py,test.py ./test.py
coverage: .coverage
	${PYTHON3} -m coverage report -m test.py dokuforge/*.py

.PHONY: all doc clean setup test check
