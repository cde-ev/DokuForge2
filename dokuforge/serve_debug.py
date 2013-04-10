#!/usr/bin/env python2
"""
Simple server listening on http://localhost:8800/ with a traceback middleware
and logging requests to stdout.

WARNING: anyone producing an exception can execute any python code via http
"""

import logging
from wsgiref.simple_server import make_server

from werkzeug.debug import DebuggedApplication

from dokuforge import buildapp

def main():
    logging.basicConfig(level=logging.DEBUG)
    app = buildapp()
    app = DebuggedApplication(app, evalex=True)
    make_server("localhost", 8800, app).serve_forever()

if __name__ == '__main__':
    main()
