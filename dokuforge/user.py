import random
import ConfigParser
import io

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
    """User-Class

    @ivar name: name of the user
    @ivar status: status of the user, valid values are as follows
        - cde_dokubeauftragter
        - cde_kursleiter
        - cde_dokuteam
        - jgw_dokubeauftragter
        - jgw_kursleiter
        - jgw_dokuteam
    @ivar password: password of the user
    @ivar permissions: dictionary of permissions, the key is the name of
        the permission, the value is a boolean, True if the permission is
        granted, False if explicitly revoked. Absence of a key means no
        permission. Some permissions grant recursive permissions (like
        akademie_read_y=True), if there is a more specific explicitly
        revoked permission (like kurs_read_y_z=False) it takes precedence
        over a recursively granted permission. The permissions are as
        follows.
         - kurs_x_y_z --
            x in {read, write}, y akademiename, z kursname

            Grants the coresponding privelege for one course. Write always
            implies read.
         - akademie_x_y --
            x in {read, write, view, meta}, y akademiename

            Grants the coresponding privelege for one academy, in the case
            of read and write implying recursively the priveleges for all
            courses of the academy. The view privelege enables the user to
            access the academy but does not grant any recursive priveleges
            (in contrast to akademie_read_* which allows to read all
            courses); it (the view privilege) is implied by the read
            privilege. The meta privelege grants the ability to modify
            academy/course titles, academy groups and the ability to create
            new courses. Write always implies read.
         - gruppe_x_y --
            x in {read, write, show, meta}, y gruppenname

            Grants the coresponding privelege for a whole group of academies
            recursively implying the priveleges for all academies of this
            group and all courses of these academies. The privelege show
            controles whether academies of the corresponding groups are
            displayed (by default only the academies of the group associated
            to the user are displayed; currently this is the
            defaultgroup()).  Write always implies read.
         - df_{read, write, show, meta} --
            Grants a global version of the corresponding privelege. This is
            a global privelege and thus not affected by explicitly revoked
            permissions. Write always implies read.
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

        In summary there are the global df_* privileges which cannot be
        revoked by more specific privileges and the tower of gruppe_*,
        akademie_* and kurs_* in ascending order of explicitness. The first
        two of which grant recursive privileges which can be revoked by a
        more explicit entry -- the most explicit applicable entry decides
        the actual privilege.

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
        ## cast None to False
        return bool(self.permissions.get(perm))

    def revokedPermission(self, perm):
        """
        check if user has an explicitly revoked permission
        @type perm: unicode
        @rtype: bool
        """
        assert isinstance(perm, unicode)
        state = self.permissions.get(perm)
        if state is not None and state == False:
            return True
        else:
            return False

    def checkReadWrite(self, aca, course, priv):
        """
        Check for read or write privileges.

        This does not enforce the rule 'write implies read', but otherwise
        works as allowedRead or allowedWrite should do.

        @type aca: Academy or LazyView
        @type course: None or Course or LazyView
        @type priv: unicode
        @param priv: either u'read' or u'write'
        @rtype: bool
        """
        ## first check global priveleges
        if self.hasPermission(u"df_%s" % priv) or self.isSuperAdmin():
            return True
        ## now we need to resolve aca and course
        ## a bit care has to be taken since we need the groups too
        if isinstance(aca, LazyView):
            groups = aca["groups"]
            aca = aca["name"]
        else:
            assert isinstance(aca, Academy)
            groups = aca.getgroups()
            aca = aca.name
        if course is None:
            pass
        elif isinstance(course, LazyView):
            course = course["name"]
        else:
            assert isinstance(course, Course)
            course = course.name
        ## second check for explicitly revoked privilege
        if course is None:
            if self.revokedPermission(u"akademie_%s_%s" % (priv, aca)):
                return False
        else:
            if self.revokedPermission(u"kurs_%s_%s_%s" % (priv, aca, course)):
                return False
            if self.revokedPermission(u"akademie_%s_%s" % (priv, aca)) and \
                not self.hasPermission(u"kurs_%s_%s_%s" % (priv, aca, course)):
                return False
        ## now we are done with revoked permissions and can continue
        ## third check group level privileges
        for g in groups:
            if self.hasPermission(u"gruppe_%s_%s" % (priv, g)):
                return True
        ## fourth check the academy level priveleges
        if self.hasPermission(u"akademie_%s_%s" % (priv, aca)):
            return True
        if course is None:
            ## no access to the whole academy
            return False
        ## at this point we ask for a write privelege of a specific course
        return self.hasPermission(u"kurs_%s_%s_%s" % (priv, aca, course))

    def allowedView(self, aca):
        """
        @type aca: Academy or LazyView
        @rtype: bool
        """
        ## first check whether we are allowed to read
        ## this include the check for global privileges (df_*)
        if self.allowedRead(aca):
            return True
        ## now we need to resolve aca
        if isinstance(aca, LazyView):
            aca = aca["name"]
        else:
            assert isinstance(aca, Academy)
            aca = aca.name
        ## second check for view privilege (this includes explicitly revocation)
        return self.hasPermission(u"akademie_view_%s" % aca)

    def allowedRead(self, aca, course = None):
        """
        @type aca: Academy or LazyView
        @type course: None or Course or LazyView
        @rtype: bool
        """
        ## first check whether we are allowed to write to enforce 'write implies read'
        if self.allowedWrite(aca, course):
            return True
        ## second check whether we are allowed to read
        return self.checkReadWrite(aca, course, u'read')

    def allowedWrite(self, aca, course = None):
        """
        @type aca: Academy or LazyView
        @type course: None or Course or LazyView
        @rtype: bool
        """
        return self.checkReadWrite(aca, course, u'write')

    def allowedMeta(self, aca):
        """
        @type aca: Academy or LazyView
        @rtype: bool
        """
        ## first check global priveleges
        if self.hasPermission(u"df_meta") or self.isSuperAdmin():
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
        ## second check for explicitly revoked privilege
        if self.revokedPermission(u"akademie_meta_%s" % aca):
            return False
        ## now we are done with revoked permissions and can continue
        ## third check group level privileges
        for g in groups:
            if self.hasPermission(u"gruppe_meta_%s" % g):
                return True
        ## fourth check the academy level priveleges
        return self.hasPermission(u"akademie_meta_%s" % aca)

    def allowedExport(self, aca):
        """
        @type aca: Academy or LazyView
        @rtype: bool
        """
        assert isinstance(aca, Academy) or isinstance(aca, LazyView)
        ## superadmin is allowed to do everything
        if self.isSuperAdmin():
            return True
        ## we require the corresponding read privelege
        if not self.allowedRead(aca):
            return False
        ## now we have to check the export privelege
        return self.hasPermission(u"df_export")

    def allowedCreate(self):
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
        # FIXME we should add support for jgw
        return u"cde"

class UserDB:
    """
    Class for the user database

    @ivar db: dictionary containing (username, User object) pairs
    @ivar storage: storage.CachingStorage object holding the userdb
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

    def load(self):
        """
        Load the user database from disk.

        This erases all in-memory changes.
        """
        ## if nothing is changed return
        if self.storage.timestamp() <= self.timestamp:
            return
        config = ConfigParser.SafeConfigParser()
        content = io.BytesIO(self.storage.content())
        ## update time, since we read the new content
        self.timestamp = self.storage.cachedtime
        config.readfp(content)
        ## clear after we read the new config, better safe than sorry
        self.db.clear()
        for name in config.sections():
            permissions = dict((perm.strip().split(' ')[0].decode("utf8"),
                                strtobool(perm.strip().split(' ')[1].decode("utf8")))
                for perm in config.get(name, 'permissions').split(','))
            self.addUser(name.decode("utf8"),
                         config.get(name, 'status').decode("utf8"),
                         config.get(name, 'password').decode("utf8"),
                         permissions)

