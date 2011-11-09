
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

.coverage:
	which coverage &> /dev/null || python-coverage -x test.py
	which python-coverag &> /dev/null || coverage -x test.py
coverage: .coverage
	which coverage &> /dev/null || python-coverage -r -m -i "dokuforge/*.py"
	which python-coverage &> /dev/null || coverage -r -m -i "dokuforge/*.py"

.PHONY: all doc clean setup test check
