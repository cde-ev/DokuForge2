
all: doc setup

doc:
	epydoc --config epydoc.conf

setup:
	python createuserdb.py
	python createacademy.py

clean:
	rm -rf html work df
	rm -f *.pyc *~

.PHONY: all doc
