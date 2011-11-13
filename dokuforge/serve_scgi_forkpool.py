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
import syslog
import traceback

def do_syslog(msg):
    syslog.syslog(syslog.LOG_ERR | syslog.LOG_DAEMON | syslog.LOG_PID, msg)

class ExceptionsToSyslog:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except:
            exc_info = sys.exc_info()
            do_syslog("Received Python exception: %s" % (exc_info[1],))
            for line in traceback.format_exc(exc_info[2]).splitlines():
                do_syslog(line)
            raise # will get 503 from apache

def main(configfile):
    config = ConfigParser.SafeConfigParser()
    config.read(configfile)
    port = int(config.get('scgi','port'))
    pc = PathConfig(config)
    app = buildapp(pc)
    app = ExceptionsToSyslog(app)
    SCGIServer(app, port).enable_sighandler().run()

if __name__ == '__main__':
    configfile = "./dokuforge.conf.sample"
    if len(sys.argv) > 1:
        configfile = sys.argv[1]
    main(configfile)
