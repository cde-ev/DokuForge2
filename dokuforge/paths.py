import ConfigParser
from cStringIO import StringIO

from dokuforge.storage import Storage
from dokuforge.user import UserDB

default_config = """
[path]
rootdir = ./work/example
dfdir = %(rootdir)s/df
admindir = %(rootdir)s/admin
sessiondbpath = :memory:
staticservepath = static/
mathjaxuri = %(staticservepath)s/mathjax/
"""

class PathConfig(object):
    section = "path"
    def __init__(self,config=None):
        if config is None:
            self.cp = ConfigParser.SafeConfigParser()
            self.cp.readfp(StringIO(default_config))
        else:
            self.cp = config

    def read(self, configfile):
        self.cp =ConfigParser.SafeConfigParser()
        with file(configfile) as opencfg:
            self.cp.readfp(opencfg)

    @property
    def rootdir(self):
        return self.cp.get(self.section, "rootdir")

    @rootdir.setter
    def rootdir(self, value):
        return self.cp.set(self.section, "rootdir", value)

    @property
    def dfdir(self):
        """path to directory storing all the documentation projects.
        Each directory within this directory represents one academy."""
        return self.cp.get(self.section, "dfdir")

    @property
    def admindir(self):
        """path to directory containing configuration files"""
        return self.cp.get(self.section, "admindir")

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
    def mathjaxuri(self):
        return self.cp.get(self.section, "mathjaxuri")

    @property
    def userdb(self):
        return UserDB(Storage(self.admindir, "userdb"))

    def loaduserdb(self):
        userdb = self.userdb
        userdb.load()
        return userdb

    @property
    def groupstore(self):
        return Storage(self.admindir, "groupdb")
