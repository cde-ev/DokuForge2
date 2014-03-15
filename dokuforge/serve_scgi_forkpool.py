#!/usr/bin/env python
"""
Forking server listening on scgi://localhost with a spamassassin like
worker model. The port to listen will be taken from the configuration file
"""

from wsgitools.scgi.forkpool import SCGIServer

from dokuforge import buildapp
from dokuforge.paths import PathConfig, config_encoding

import ConfigParser
import io
import sys
import syslog
import resource
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

def parsesize(s):
    f = 1
    if s.lower().endswith(u'k'):
        s = s[:-1]
        f = 1024
    elif s.lower().endswith(u'm'):
        s = s[:-1]
        f = 1024*1024
    return int(float(s) * f)

def main(configfile):
    config = ConfigParser.SafeConfigParser()
    with io.open(configfile, encoding=config_encoding) as openconfig:
        config.readfp(openconfig)
    port = int(config.get(u'scgi', u'port'))
    limitas = parsesize(config.get(u'scgi', u'limitas'))
    limitdata = parsesize(config.get(u'scgi', u'limitdata'))
    maxworkers = int(config.get(u'scgi', u'maxworkers'))
    limitnprocoffset = int(config.get(u'scgi', u'limitnprocoffset'))
    # one rcs process per worker + one spawner from wsgitools
    limitnproc = 2 * maxworkers + 1 + limitnprocoffset
    resource.setrlimit(resource.RLIMIT_AS, (limitas, limitas))
    resource.setrlimit(resource.RLIMIT_DATA, (limitdata, limitdata))
    resource.setrlimit(resource.RLIMIT_NPROC, (limitnproc, limitnproc))
    pc = PathConfig(config)
    app = buildapp(pc)
    app = ExceptionsToSyslog(app)
    SCGIServer(app, port).enable_sighandler().run()

if __name__ == '__main__':
    configfile = "./dokuforge.conf.sample"
    if len(sys.argv) > 1:
        configfile = sys.argv[1]
    main(configfile)
