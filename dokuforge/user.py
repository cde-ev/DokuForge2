import random
import ConfigParser
from cStringIO import StringIO

sysrand = random.SystemRandom()

from dokuforge.common import strtobool, epoch
from dokuforge.course import Course
from dokuforge.academy import Academy
from dokuforge.view import LazyView

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
    @ivar status: status of the user, valid values are as follows
        - cde_dokubeauftragter
        - cde_kursleiter
        - cde_dokuteam
    @ivar password: password of the user
    @ivar permissions: dictionary of permissions, the key is the name of
        the permission, the value is a boolean, True if the permission is
        granted, False if explicitly revoked. Absence of a key means no
        permission. The permissions are as follows.
         - kurs_x_y_z --
            x in {read, write}, y akademiename, z kursname

            Grants the coresponding privelege for one course. Write does
            never imply read.
         - akademie_x_y --
            x in {read, write, view}, y akademiename

            Grants the coresponding privelege for one academy, in the case
            of read and write implying the priveleges for all courses of the
            academy. Having write priveleges for an academy enables a user
            to create courses. The view privelege enables the user to access
            the academy but does not grant any recursive priveleges (in
            contrast to akademie_read_* which allows to read all courses).
         - gruppe_x_y --
            x in {read, write, show}, y gruppenname

            Grants the coresponding privelege for a whole group of academies
            implying the priveleges for all academies of this group and all
            courses of these academies. The privelege show controles whether
            academies of the corresponding groups are displayed.
         - df_{read, write, show} --
            Grants a global version of the corresponding privelege.
         - df_export --
            Grants the privelege to export academies. Requires the
            corresponding read privilege
         - df_create --
            Grants the privelege to create academies.
         - df_admin --
            Grants the admin privelege. This enables the user management. But
            not the ability to modify admin status or admin accounts.
            (This restriction is not yet implemented.)
         - df_superadmin --
            Grants all priveleges.
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

    def allowedRead(self, aca, course = None, recursive = False):
        """
        @type aca: Academy or LazyView
        @type course: None or Course or LazyView
        @type recursive: bool
        @param recursive: check for recursive read priveleges. This means that
            akademie_view_* is not enough.
        @rtype: bool
        """
        ## first check global priveleges
        if self.hasPermission(u"df_read") or self.isSuperAdmin():
            return True
        ## now we need to resolve aca
        ## a bit care has to be taken since we need the groups too
        if isinstance(aca, LazyView):
            groups = aca["groups"]
            aca = aca["name"]
        else:
            assert isinstance(aca, Academy)
            groups = aca.getgroups()
            aca = aca.name
        ## second check group level privileges
        for g in groups:
            if self.hasPermission(u"gruppe_read_%s" % g):
                return True
        ## third check the academy level priveleges
        if self.hasPermission(u"akademie_read_%s" % aca):
            return True
        if course is None:
            ## we only want to read an academy entry
            ## we now have to check the akademie_view privelege
            ## but in recursive case this is not sufficient
            if recursive:
                return False
            ## in non-recursive case we check akademie_view_*
            return self.hasPermission(u"akademie_view_%s" % aca)
        ## at this point we ask for a read privelege of a specific course
        ## so we resolve course
        elif isinstance(course, LazyView):
            course = course["name"]
        else:
            assert isinstance(course, Course)
            course = course.name
        return self.hasPermission(u"kurs_read_%s_%s" % (aca, course))

    def allowedWrite(self, aca, course = None):
        """
        @type aca: Academy or LazyView
        @type course: None or Course or LazyView
        @rtype: bool
        """
        ## first check global priveleges
        if self.hasPermission(u"df_write") or self.isSuperAdmin():
            return True
        ## now we need to resolve aca
        ## a bit care has to be taken since we need the groups too
        if isinstance(aca, LazyView):
            groups = aca["groups"]
            aca = aca["name"]
        else:
            assert isinstance(aca, Academy)
            groups = aca.getgroups()
            aca = aca.name
        ## second check group level privileges
        for g in groups:
            if self.hasPermission(u"gruppe_write_%s" % g):
                return True
        ## third check the academy level priveleges
        if self.hasPermission(u"akademie_write_%s" % aca):
            return True
        if course is None:
            ## no write access to the academy
            return False
        ## at this point we ask for a write privelege of a specific course
        ## so we resolve course
        elif isinstance(course, LazyView):
            course = course["name"]
        else:
            assert isinstance(course, Course)
            course = course.name
        return self.hasPermission(u"kurs_write_%s_%s" % (aca, course))

    def mayExport(self, aca):
        """
        @type aca: Academy or LazyView
        @rtype: bool
        """
        assert isinstance(aca, Academy) or isinstance(aca, LazyView)
        ## superadmin is allowed to do everything
        if self.isSuperAdmin():
            return True
        ## we require the corresponding read privelege
        ## akademie_view_* shall not be enough, hence we demand recursive
        if not self.allowedRead(aca, recursive = True):
            return False
        ## now we have to check the export privelege
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
                self.hasPermission(u"gruppe_show_%s" % groupname)

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
        Return the default group of a user. Currently this is a trivial
        function since we have just one possible group at the moment. This
        could be expanded in the future.

        @rtype: unicode
        """
        return u"cde"

class UserDB:
    """
    Class for the user database

    @ivar db: dictionary containing (username, User object) pairs
    @ivar storage: storage.Storage object holding the userdb
    @ivar timestamp: time of last update, this is compared to the mtime of
        the CachingStorage
    """
    def __init__(self, storage):
        """
        @type storage: storage.Storage
        """
        self.db = dict()
        self.storage = storage
        self.timestamp = epoch

    def addUser(self, name, status, password, permissions):
        """
        add a user to the database in memory

        @type name: unicode
        @type status: unicode
        @type password: unicode
        @param permissions: dictionary of permissions
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
        @type password: unicode
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
        ## if nothing is changed return
        if self.storage.timestamp() <= self.timestamp:
            return
        config = ConfigParser.SafeConfigParser()
        content = StringIO(self.storage.content())
        ## update time, since we read the new content
        self.timestamp = self.storage.cachedtime
        config.readfp(content)
        ## clear after we read the new config, better safe than sorry
        self.db.clear()
        for name in config.sections():
            # FIXME: the following line raises NoOptionError
            # To reproduce this problem go to admin, enter a configuration file
            # with valid syntax, but with an empty section. It passes the
            # tryConfigParser method of Application and later fails to load
            # here.
            permissions = dict((perm.strip().split(' ')[0].decode("utf8"),
                                strtobool(perm.strip().split(' ')[1].decode("utf8")))
                for perm in config.get(name, 'permissions').split(','))
            self.addUser(name.decode("utf8"),
                         config.get(name, 'status').decode("utf8"),
                         config.get(name, 'password').decode("utf8"),
                         permissions)

