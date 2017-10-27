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

# entire test suite
test: test.py
	${PYTHON2} test.py

# only test exporting of text (microtypography, titles etc.)
test-exported-strings:
	${PYTHON2} -m unittest test.DokuforgeMicrotypeUnitTests test.DokuforgeTitleParserTests test.DokuforgeCaptionParserTests

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON2} -m coverage -x test.py
coverage: .coverage
	${PYTHON2} -m coverage -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
