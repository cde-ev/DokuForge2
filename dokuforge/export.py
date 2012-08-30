#!/usr/bin/env python
"""
Usage: python -m dokuforge.export academy_or_course_directory
"""

import os.path
import sys

from dokuforge.course import Course
from dokuforge.parser import dfLineGroupParser

class PseudoTarWriter:
    def __init__(self, directory):
        self.directory = directory

    def addChunk(self, filename, content):
        # Drop leading component. It is contained both in self.directory and in
        # filename.
        filename = filename.split('/', 1)[1]
        with open(os.path.join(self.directory, filename), "w") as output:
            output.write(content)

def process_course(directory):
    print("Processing %s..." % directory)
    tw = PseudoTarWriter(directory)
    c = Course(directory)
    for _ in c.texExportIterator(tw):
        pass

def process(directory):
    if os.path.exists(os.path.join(directory, "Index,v")):
        process_course(directory)
    else:
        for elem in os.listdir(directory):
            entry = os.path.join(directory, elem)
            if os.path.isdir(entry):
                process(entry)

def main():
    basedir = sys.argv[1]
    process(basedir)

if __name__ == "__main__":
    main()
