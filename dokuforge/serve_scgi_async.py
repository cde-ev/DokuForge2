#!/usr/bin/env python
"""
Moderate server listening on scgi://localhost:4000/ with an asynchronous worker.
"""

from wsgitools.scgi.asynchronous import SCGIServer

from dokuforge import buildapp


def main() -> None:
    app = buildapp()
    SCGIServer(app, 4000).run()

if __name__ == '__main__':
    main()
