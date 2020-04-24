ifneq ($(shell which python2),)
PYTHON3 ?= python2
else
PYTHON3 ?= python3
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

# entire test suite
test: test.py
	${PYTHON3} test.py

# only test exporting of text (microtypography, titles etc.)
test-exported-strings:
	${PYTHON3} -m unittest test.DokuforgeParserUnitTests test.DokuforgeMicrotypeUnitTests test.DokuforgeTitleParserTests test.DokuforgeCaptionParserTests

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON3} -m coverage -x test.py
coverage: .coverage
	${PYTHON3} -m coverage -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
