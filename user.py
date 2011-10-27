import random
import ConfigParser
from cStringIO import StringIO

sysrand = random.SystemRandom()

from common import strtobool
from course import CourseLite
from academy import AcademyLite

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
                       df_x ... x in {superadmin, admin, show, read, write, show_cde, read_cde, write_cde, export, create}
    """
    def __init__(self, name, status, password, permissions):
        """
        User-Class Constructor

        @type name: unicode
        @type status: unicode
        @type password: unicode or None
        @param password: a plaintext password or None if it should be generated
        @type permissions: dictionary of permissions
        """
        assert isinstance(name, unicode)
        assert isinstance(status, unicode)
        assert password is None or isinstance(password, unicode)
        self.name = name
        self.status = status
        if password is None:
            password = randpasswordstring(6).decode("utf8")
        self.password = password
        self.permissions = permissions
    def hasPermission(self, perm):
        """
        check if user has a permission
        @type perm: unicode
        @rtype: bool
        """
        assert isinstance(perm, unicode)
        return bool(self.permissions.get(perm))

    def allowedRead(self, aca, course = None):
        """
        @type aca: AcademyLite
        @type course: None or CourseLite
        @rtype: bool
        """
        assert isinstance(aca, AcademyLite)
        assert course is None or isinstance(course, CourseLite)
        if self.hasPermission(u"df_read") or self.isSuperAdmin():
            return True
        for g in aca.getgroups():
            if self.hasPermission(u"df_read_" + g):
                return True
        if course is None:
            return self.hasPermission(u"akademie_read_%s" % aca.name)
        else:
            return self.hasPermission(u"akademie_read_%s_%s" % (aca.name, course.name))

    def allowedWrite(self, aca, course = None):
        """
        @type aca: AcademyLite
        @type course: None or CourseLite
        @rtype: bool
        """
        assert isinstance(aca, AcademyLite)
        assert course is None or isinstance(course, CourseLite)
        if self.hasPermission(u"df_write") or self.isSuperAdmin():
            return True
        for g in aca.getgroups():
            if self.hasPermission(u"df_write_" + g):
                return True
        if course is None:
            return self.hasPermission(u"akademie_write_%s" % aca.name)
        else:
            return self.hasPermission(u"akademie_write_%s_%s" % (aca.name, course.name))

    def mayExport(self, aca):
        """
        @type aca: AcademyLite
        @rtype: bool
        """
        assert isinstance(aca, AcademyLite)
        if self.isSuperAdmin():
            return True
        if not self.allowedRead(aca):
            return False
        return self.hasPermission(u"df_export")

    def mayCreate(self):
        """
        @rtype: bool
        """
        return self.hasPermission(u"df_create") or self.isSuperAdmin()

    def allowedList(self, groupname):
        """
        @type groupname: unicode
        @rtype: bool
        """
        assert isinstance(groupname, unicode)
        return self.isSuperAdmin() or self.hasPermission(u"df_show") or \
                self.hasPermission(u"df_show_" + groupname)

    def isAdmin(self):
        """
        @rtype: bool
        """
        return self.isSuperAdmin() or self.hasPermission(u"df_admin")

    def isSuperAdmin(self):
        """
        @rtype: bool
        """
        return self.hasPermission(u"df_superadmin")

    def defaultGroup(self):
        """
        @rtype: unicode
        """
        return u"cde"

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
        add a user to the database in memory

        @type name: unicode
        @type status: unicode
        @type password: unicode
        @param permissins: dictionary of permissions
        @type permissions: {unicode: bool}
        """
        assert isinstance(name, unicode)
        assert isinstance(status, unicode)
        assert isinstance(password, unicode)
        assert all(isinstance(key, unicode) and isinstance(value, bool)
                   for key, value in permissions.items())
        if name in self.db:
            return False
        self.db[name] = User(name, status, password, permissions)
        return True

    def modifyUser(self, name, attributes):
        """
        modify a user of the database in memory

        @type name: unicode
        @type attributes: {unicode: unicode}
        @param attributes: dictionary of changes to apply, sytax is: (action,
                          value) where action is one of 'status',
                          'password', 'permission_grant',
                          'permission_revoke'
        """
        assert isinstance(name, unicode)
        assert all(isinstance(key, unicode) and isinstance(value, unicode)
                   for key, value in attributes.items())
        if not name in self.db:
            return False
        for (attr_name, attr_value) in attributes.items():
            if attr_name == u"status":
                self.db[name].status = attr_value
            elif attr_name == u"password":
                self.db[name].password = attr_value
            elif attr_name == u"permission_grant":
                self.db[name].permissions[attr_value] = True
            elif attr_name == u"permission_revoke":
                self.db[name].permissions[attr_value] = False
            else:
                print "Unknown attribute", attr_name, "w/ value", attr_value

    def checkLogin(self, name, password):
        """
        @type name: unicode
        @type passwordn: unicode
        @returns: True if name and password match an existing user, False otherwise
        """
        assert isinstance(name, unicode)
        assert isinstance(password, unicode)
        try:
            return self.db[name].password == password
        except KeyError:
            return False

    def store(self):
        """
        Store the user database on disk.

        We use ConfigParser and the accompanying format.
        """
        config = ConfigParser.SafeConfigParser()
        content = StringIO()
        for name in self.db:
            ename = name.encode("utf8")
            config.add_section(ename)
            config.set(ename, 'name', self.db[name].name.encode("utf8"))
            config.set(ename, 'status', self.db[name].status.encode("utf8"))
            config.set(ename, 'password', self.db[name].password.encode("utf8"))
            permstr = u','.join(u'%s %r' % t for t in
                                self.db[ename].permissions.items()) \
                    .encode("utf8")
            config.set(ename, 'permissions', permstr)
        config.write(content)
        ## seek to the start, so we know what to store
        content.seek(0)
        self.storage.store(content)

    def load(self):
        """
        Load the user database from disk.

        This erases all in-memory changes.
        """
        config = ConfigParser.SafeConfigParser()
        content = StringIO(self.storage.content())
        config.readfp(content)
        # clear after we read the new config, better safe than sorry
        self.db.clear()
        for name in config.sections():
            permissions = dict((perm.split(' ')[0].decode("utf8"),
                                strtobool(perm.split(' ')[1].decode("utf8")))
                for perm in config.get(name, 'permissions').split(','))
            self.addUser(config.get(name, 'name').decode("utf8"),
                         config.get(name, 'status').decode("utf8"),
                         config.get(name, 'password').decode("utf8"),
                         permissions)
