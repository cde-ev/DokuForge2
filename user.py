import random
import ConfigParser
from cStringIO import StringIO

sysrand = random.SystemRandom()

from common import strtobool

def randpasswordstring(n=6):
    """
    @returns: random string of length n which is easily readable
    @type n: int
    @rtype: str
    """
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz123456789'
    return ''.join(sysrand.choice(chars) for x in range(n))


class User:
    """
    User-Class

    @ivar name: name of the user
    @ivar status: status of the user, valid values are: dokubeauftragter,
                  kursleiter, dokuteam
    @ivar password: password of the user
    @ivar permissions: dictionary of permissions, the syntax is as follows:
                       akademie_x_y_z ... x in {read, write}, y akademiename, z kursname
                       df_x ... x in {admin, useradmin, dokuteam}
    """
    def __init__(self, name, status, password, permissions):
        """
        User-Class Constructor

        @type name: str
        @type status: str
        @type password: str
        @type permissions: dictionary of permissions
        """
        self.name = name
        self.status = status
        if password == "":
            password = randpasswordstring(6)
        self.password = password
        self.permissions = permissions
    def hasPermission(self, perm):
        """
        check if user has a permission
        """
        if not perm in self.permissions:
            return False
        if self.permissions[perm]:
            return True
        return False

    def allowedRead(self, acaname, coursename = None):
        if coursename is None:
            return self.hasPermission("akademie_read_%s" % acaname)
        else:
            return self.hasPermission("akademie_read_%s_%s" % (acaname, coursename))

    def allowedWrite(self, acaname, coursename = None):
        if coursename is None:
            return self.hasPermission("akademie_write_%s" % acaname)
        else:
            return self.hasPermission("akademie_write_%s_%s" % (acaname, coursename))



class UserDB:
    """
    Class for the user database

    @ivar db: dictionary containing (username, User object) pairs
    @ivar storage: storage.Storage object holding the userdb
    """
    def __init__(self, storage):
        """
        @type storage: storage.Storage
        """
        self.db = dict()
        self.storage = storage
    def addUser(self, name, status, password, permissions):
        """
        add a user to the database

        @type name: str
        @type status: str
        @type password: str
        @type permissins: dictionary of permissions
        """
        if name in self.db:
            return False
        self.db[name] = User(name, status, password, permissions)
        return True
    def modifyUser(self, name, attributes):
        """
        modify a user of the database

        @type name: str
        @type attributes: dictionary of changes to apply, sytax is: (action,
                          value) where action is one of 'status',
                          'password', 'permission_grant',
                          'permission_revoke'
        """
        if not name in self.db:
            return False
        for (attr_name, attr_value) in attributes:
            if attr_name == "status":
                self.db[name].status = attr_value
            elif attr_name == "password":
                self.db[name].password = attr_value
            elif attr_name == "permission_grant":
                self.db[name].permissions[attr_value] = True
            elif attr_name == "permission_revoke":
                self.db[name].permissions[attr_value] = False
            else:
                print "Unknown attribute", attr_name, "w/ value", attr_value
    def checkLogin(self, name, password):
        """
        @type name: str
        @type passwordn: str
        @returns: True if name and password match an existing user, False otherwise
        """
        try:
            return self.db[name].password == password
        except KeyError:
            return False

    def store(self):
        config = ConfigParser.SafeConfigParser()
        content = StringIO()
        for name in self.db:
            config.add_section(name)
            config.set(name, 'name', self.db[name].name)
            config.set(name, 'status', self.db[name].status)
            config.set(name, 'password', self.db[name].password)
            permstr = ','.join('%s %s' % t for t in
                               self.db[name].permissions.items())
            config.set(name, 'permissions', permstr)
        config.write(content)
        self.storage.store(content.getvalue())

    def load(self):
        config = ConfigParser.SafeConfigParser()
        content = StringIO(self.storage.content())
        config.readfp(content)
        # clear after we read the new config, better safe than sorry
        self.db.clear()
        for name in config.sections():
            permissions = dict((perm.split(' ')[0],
                                strtobool(perm.split(' ')[1]))
                for perm in config.get(name, 'permissions').split(','))
            self.addUser(config.get(name, 'name'), config.get(name,
                                                              'status'),
                         config.get(name, 'password'), permissions)
