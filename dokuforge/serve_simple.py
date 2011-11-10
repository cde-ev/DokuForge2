#!/usr/bin/env python
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
