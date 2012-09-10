# Copyright (c) 2012, Klaus Aehlig, Helmut Grohne, Markus Oehme
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the three-clause BSD license.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# You should have received a copy of the Three-Clause BSD License
# along with this program in the file COPYING.
# If not, see <http://opensource.org/licenses/bsd-3-clause>

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

.coverage:$(wildcard dokuforge/*.py) test.py
	${PYTHON_COVERAGE} -x test.py
coverage: .coverage
	${PYTHON_COVERAGE} -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
