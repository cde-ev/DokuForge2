#!/usr/bin/env python

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
"""
Simple server listening on http://localhost:8800/ with a traceback middleware
and logging requests to stdout.
"""

from ConfigParser import SafeConfigParser
import sys
from wsgiref.simple_server import make_server

from wsgitools.middlewares import TracebackMiddleware

from dokuforge import buildapp
from dokuforge.paths import PathConfig

def main():
    configfile = "./dokuforge.conf.sample"
    if len(sys.argv) > 1:
        configfile = sys.argv[1]
    config = SafeConfigParser()
    config.read(configfile)
    pc = PathConfig(config)
    app = buildapp(pc)
    app = TracebackMiddleware(app)
    make_server("localhost", 8800, app).serve_forever()

if __name__ == '__main__':
    main()
