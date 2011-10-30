#!/usr/bin/env python
"""
Forking server listening on scgi://localhost:4000/ with a spamassassin like
worker model.
"""

from wsgitools.scgi.forkpool import SCGIServer

from dokuforge import buildapp
from dokuforge.paths import PathConfig

def main():
    pc = PathConfig()
    pc.sessiondbpath = "%(workdir)s/sessiondb.sqlite3"
    app = buildapp(pc)
    SCGIServer(app, 4000).enable_sighandler().run()

if __name__ == '__main__':
    main()
