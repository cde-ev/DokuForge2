#!/usr/bin/env python
"""
Usage: python -m dokuforge.export df2_academy_directory dokuforge-export-static_directory academy_name
"""

import os.path
import sys

from dokuforge.course  import Course
from dokuforge.parser  import dfLineGroupParser
from dokuforge.academy import Academy
from dokuforge.common  import TarWriter

from tarfile import TarFile

'''
# currently not needed
class PseudoTarWriter:
    def __init__(self, directory):
        self.directory = directory

    def addChunk(self, filename, content, lastchanged):
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
'''

def process(academiesdir,staticexportdir,academyname):
    academy = Academy ( os.path.join(academiesdir,academyname), [] )

    # duplicate code from application.py
    prefixdir = b"texexport_" + academyname

    def export_iterator(aca, staticexpdir, prefix):
        tarwriter = TarWriter(gzip=False)
        tarwriter.pushd(prefix)
        for chunk in aca.texExportIterator(tarwriter,
                                           static=staticexpdir):
            yield chunk
        tarwriter.popd()
        yield tarwriter.close()

    tarGenerator = export_iterator(academy,staticexportdir,prefixdir)

    outputfile = open ( prefixdir+'.tar', 'w' )

    for chunk in tarGenerator:
        outputfile.write(chunk)

def main():
    academiesdir    = sys.argv[1]
    staticexportdir = sys.argv[2]
    academyname     = sys.argv[3]
    process(academiesdir,staticexportdir,academyname)

if __name__ == "__main__":
    main()
