#!/usr/bin/env python
"""
Simple server listening on http://localhost:8800/ with a traceback middleware
and logging requests to stdout.
"""
import sys
from wsgiref.simple_server import make_server

from wsgitools.middlewares import TracebackMiddleware

from dokuforge import buildapp
from dokuforge.paths import PathConfig


def main() -> None:
    configfile = "./dokuforge.conf.sample"
    if len(sys.argv) > 1:
        configfile = sys.argv[1]
    pc = PathConfig()
    pc.read(configfile)
    app = buildapp(pc)
    app = TracebackMiddleware(app)
    make_server("localhost", 8800, app).serve_forever()

if __name__ == '__main__':
    main()
