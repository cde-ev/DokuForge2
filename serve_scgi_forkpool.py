#!/usr/bin/env python
"""
Forking server listening on scgi://localhost:4000/ with a spamassassin like
worker model.
"""

from wsgitools.scgi.forkpool import SCGIServer

from dokuforge import buildapp

def main():
    app = buildapp(sessiondbpath="./work/sessiondb.sqlite3")
    SCGIServer(app, 4000).enable_sighandler().run()

if __name__ == '__main__':
    main()
