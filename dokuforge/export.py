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

    outputfile = open ( prefixdir.decode("utf8")+'.tar', 'wb' )

    for chunk in tarGenerator:
        outputfile.write(chunk)

def main():
    academiesdir    = sys.argv[1].encode("utf8")
    staticexportdir = sys.argv[2].encode("utf8")
    academyname     = sys.argv[3].encode("utf8")
    process(academiesdir,staticexportdir,academyname)

if __name__ == "__main__":
    main()
