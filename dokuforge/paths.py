try:
    from ConfigParser import SafeConfigParser as ConfigParser
except ImportError:
    from configparser import ConfigParser
import io

from dokuforge.storage import CachingStorage
from dokuforge.user import UserDB

config_encoding = "iso-8859-1"
# "iso-8859-1" is a safe choice in the sense that
# b.decode(config_encoding).encode(config_encoding) is guarantueed to succeed.

default_config = b"""
[path]
rootdir = ./work/example
dfdir = %(rootdir)s/df
admindir = %(rootdir)s/admin
staticexportdir = %(rootdir)s/exportstatic
sessiondbpath = :memory:
staticservepath = static/
mathjaxuri = %(staticservepath)s/mathjax/
""".decode(config_encoding)

class PathConfig(object):
    section = "path"
    def __init__(self,config=None):
        if config is None:
            self.cp = ConfigParser()
            self.cp.readfp(io.StringIO(default_config))
        else:
            self.cp = config

    def read(self, configfile):
        self.cp = ConfigParser()
        # can be switched to plain open when dropping support for Python2.X
        with io.open(configfile, encoding=config_encoding) as opencfg:
            self.cp.readfp(opencfg)

    @property
    def rootdir(self):
        return self.cp.get(self.section, "rootdir").encode(config_encoding)

    @rootdir.setter
    def rootdir(self, value):
        return self.cp.set(self.section, "rootdir",
                           value.decode(config_encoding))

    @property
    def dfdir(self):
        """path to directory storing all the documentation projects.
        Each directory within this directory represents one academy."""
        return self.cp.get(self.section, "dfdir").encode(config_encoding)

    @property
    def admindir(self):
        """path to directory containing configuration files"""
        return self.cp.get(self.section, "admindir").encode(config_encoding)

    @property
    def staticexportdir(self):
        return self.cp.get(self.section, "staticexportdir").encode(
                config_encoding)

    @property
    def sessiondbpath(self):
        """path to a sqlite3 database dedicated to storing session
        cookies. Unless a forking server is used ":memory:" is fine.
        Unlike most other properties, this is a str properties."""
        return self.cp.get(self.section, "sessiondbpath")

    @sessiondbpath.setter
    def sessiondbpath(self, value):
        self.cp.set(self.section, "sessiondbpath", value)

    @property
    def staticservepath(self):
        """Unicode property!"""
        return self.cp.get(self.section, "staticservepath")

    @property
    def mathjaxuri(self):
        """Unicode property!"""
        return self.cp.get(self.section, "mathjaxuri")

    @property
    def userdb(self):
        return UserDB(self.userdbstore)

    @property
    def userdbstore(self):
        return CachingStorage(self.admindir, b"userdb")

    def loaduserdb(self):
        userdb = self.userdb
        userdb.load()
        return userdb

    @property
    def groupstore(self):
        return CachingStorage(self.admindir, b"groupdb")
