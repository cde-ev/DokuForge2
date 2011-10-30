import ConfigParser
from cStringIO import StringIO

from dokuforge.storage import Storage
from dokuforge.user import UserDB

default_config = """
[dokuforge]
rootdir = .
dfdir = %(rootdir)s/df
workdir = %(rootdir)s/work
sessiondbpath = :memory:
staticservepath = /static/
"""

class PathConfig(object):
    section = "dokuforge"
    def __init__(self):
        self.cp = ConfigParser.SafeConfigParser()
        self.cp.readfp(StringIO(default_config))

    def read(self, configfile):
        self.cp =ConfigParser.SafeConfigParser()
        with file(configfile) as opencfg:
            self.cp.readfp(opencfg)

    @property
    def rootdir(self):
        return self.cp.get(self.section, "rootdir")

    @property
    def dfdir(self):
        """path to directory storing all the documentation projects.
        Each directory within this directory represents one academy."""
        return self.cp.get(self.section, "dfdir")

    @property
    def workdir(self):
        """path to directory containing configuration files"""
        return self.cp.get(self.section, "workdir")

    @property
    def sessiondbpath(self):
        """path to a sqlite3 database dedicated to storing session
        cookies. Unless a forking server is used ":memory:" is fine."""
        return self.cp.get(self.section, "sessiondbpath")

    @sessiondbpath.setter
    def sessiondbpath(self, value):
        self.cp.set(self.section, "sessiondbpath", value)

    @property
    def staticservepath(self):
        return self.cp.get(self.section, "staticservepath")

    @property
    def userdb(self):
        return UserDB(Storage(self.workdir, "userdb"))

    def loaduserdb(self):
        userdb = self.userdb
        userdb.load()
        return userdb

    @property
    def groupstore(self):
        return Storage(self.workdir, "groupdb")
