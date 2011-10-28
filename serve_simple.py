#!/usr/bin/env python
"""
Simple server listening on http://localhost:8800/ with a traceback middleware
and logging requests to stdout.
"""

from wsgiref.simple_server import make_server

from wsgitools.middlewares import TracebackMiddleware

from dokuforge import buildapp

def main():
    app = buildapp()
    app = TracebackMiddleware(app)
    make_server("localhost", 8800, app).serve_forever()

if __name__ == '__main__':
    main()
