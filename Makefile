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

# entire test suite
test: test.py
	${PYTHON3} test.py

# only test exporting of text (microtypography, titles etc.)
test-exported-strings:
	${PYTHON3} test.py DokuforgeParserUnitTests DokuforgeMicrotypeUnitTests DokuforgeTitleParserTests DokuforgeCaptionParserTests

test-exporter: test-exported-strings
	${PYTHON3} test.py DokuforgeExporterTests LocalExportScriptTest

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON3} -m coverage run --include=dokuforge/*.py,test.py ./test.py
coverage: .coverage
	${PYTHON3} -m coverage report -m test.py dokuforge/*.py


DOKUFORGE_COMMIT_ID = $(shell git rev-parse HEAD)
docker-build:
	docker build -f .dockerfile-ubuntu-20.04  . -t dokuforge:ubuntu-20.04  --build-arg DOKUFORGE_COMMIT_ID=$(DOKUFORGE_COMMIT_ID)
	docker build -f .dockerfile-python-latest . -t dokuforge:python-latest --build-arg DOKUFORGE_COMMIT_ID=$(DOKUFORGE_COMMIT_ID)

test-in-docker: docker-build
	docker run --rm dokuforge:ubuntu-20.04  make check
	docker run --rm dokuforge:python-latest make coverage
# TODO why do we run different tests and not require coverage to be installed in the ubuntu-based image?

start: setup
	cp -r /usr/share/javascript/mathjax dokuforge/static/
	cp dokuforge.conf.sample dokuforge.conf
	python3 -m dokuforge.serve_simple dokuforge.conf

start-in-docker: docker-build
	docker run -d --network host dokuforge:python-latest make start

.PHONY: all doc clean setup test check
