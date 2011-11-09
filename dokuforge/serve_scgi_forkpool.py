#!/usr/bin/env python
"""
Forking server listening on scgi://localhost with a spamassassin like
worker model. The port to listen will be taken from the configuration file
"""

from wsgitools.scgi.forkpool import SCGIServer

from dokuforge import buildapp
from dokuforge.paths import PathConfig

import ConfigParser
import sys

def main(configfile):
    config = ConfigParser.SafeConfigParser()
    config.read(configfile)
    port = int(config.get('scgi','port'))
    pc = PathConfig(config)
    app = buildapp(pc)
    SCGIServer(app, port).enable_sighandler().run()

if __name__ == '__main__':
    configfile = "./dokuforge.conf.sample"
    if len(sys.argv) > 1:
        configfile = sys.argv[1]
    main(configfile)
