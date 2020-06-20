import configparser
import random
import typing

sysrand = random.SystemRandom()

from dokuforge.common import strtobool, epoch
from dokuforge.course import Course
from dokuforge.academy import Academy
from dokuforge.storage import CachingStorage
from dokuforge.view import LazyView


def randpasswordstring(n: int = 6) -> str:
    """
    @returns: random string of length n which is easily readable
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

            Grants the coresponding privelege for one course. Write does
            never imply read.
         - akademie_x_y --
            x in {read, write, view, meta}, y akademiename

            Grants the coresponding privelege for one academy, in the case
            of read and write implying recursivelythe priveleges for all
            courses of the academy. The view privelege enables the user to
            access the academy but does not grant any recursive priveleges
            (in contrast to akademie_read_* which allows to read all
            courses). The meta privelege grants the ability to modify
            academy/course titles, academy groups and the ability to create
            new courses.
         - gruppe_x_y --
            x in {read, write, show, meta}, y gruppenname

            Grants the coresponding privelege for a whole group of academies
            recursively implying the priveleges for all academies of this
            group and all courses of these academies. The privelege show
            controles whether academies of the corresponding groups are
            displayed (by default only the academies of the group associated
            to the user are displayed; currently this is the
            defaultgroup()).
         - df_{read, write, show, meta} --
            Grants a global version of the corresponding privelege. This is
            a global privelege and thus not affected by explicitly revoked
            permissions.
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
    def __init__(self, name: str, status: str, password: typing.Optional[str],
                 permissions) -> None:
        """
        User-Class Constructor

        @param password: a plaintext password or None if it should be generated
        @type permissions: dictionary of permissions
        """
        assert isinstance(name, str)
        assert isinstance(status, str)
        assert password is None or isinstance(password, str)
        self.name = name
        self.status = status
        if password is None:
            password = randpasswordstring(6)
        self.password = password
        self.permissions = permissions

    def hasPermission(self, perm: str) -> bool:
        """
        check if user has a permission
        """
        assert isinstance(perm, str)
        ## cast None to False
        return bool(self.permissions.get(perm))

    def revokedPermission(self, perm: str) -> bool:
        """
        check if user has a permission
        """
        assert isinstance(perm, str)
        state = self.permissions.get(perm)
        if state is not None and state == False:
            return True
        else:
            return False

    def allowedRead(self, aca: typing.Union[Academy, LazyView],
                    course: typing.Optional[typing.Union[Course,
                                                         LazyView]] = None,
                    recursive: bool = False) -> bool:
        """
        @param recursive: check for recursive read priveleges. This means that
            akademie_view_* is not enough.
        """
        ## first check global priveleges
        if self.hasPermission("df_read") or self.isSuperAdmin():
            return True
        ## now we need to resolve aca and course
        ## a bit care has to be taken since we need the groups too
        if isinstance(aca, LazyView):
            groups = aca["groups"]
            acaname = aca["name"].decode("ascii")
        else:
            assert isinstance(aca, Academy)
            groups = aca.getgroups()
            acaname = aca.name.decode("ascii")
        if course is None:
            pass
        elif isinstance(course, LazyView):
            coursename = course["name"].decode("ascii")
        else:
            assert isinstance(course, Course)
            coursename = course.name.decode("ascii")
        ## second check for explicitly revoked privilege
        if course is None:
            if self.revokedPermission("akademie_read_%s" % acaname) or \
               self.revokedPermission("akademie_view_%s" % acaname):
                return False
        else:
            if self.revokedPermission("kurs_read_%s_%s" %
                                      (acaname, coursename)):
                return False
            if self.revokedPermission("akademie_read_%s" % acaname) and \
               not self.hasPermission("kurs_read_%s_%s" %
                                      (acaname, coursename)):
                return False
        ## now we are done with revoked permissions and can continue
        ## third check group level privileges
        for g in groups:
            if self.hasPermission("gruppe_read_%s" % g):
                return True
        ## fourth check the academy level priveleges
        if self.hasPermission("akademie_read_%s" % acaname):
            return True
        if course is None:
            ## we only want to read an academy entry
            ## we now have to check the akademie_view privelege
            ## but in recursive case this is not sufficient
            if recursive:
                return False
            ## in non-recursive case we check akademie_view_*
            return self.hasPermission("akademie_view_%s" % acaname)
        ## at this point we ask for a read privelege of a specific course
        return self.hasPermission("kurs_read_%s_%s" % (acaname, coursename))

    def allowedWrite(self, aca: typing.Union[Academy, LazyView],
                     course: typing.Optional[
                         typing.Union[Course, LazyView]] = None) -> bool:
        ## first check global priveleges
        if self.hasPermission("df_write") or self.isSuperAdmin():
            return True
        ## now we need to resolve aca and course
        ## a bit care has to be taken since we need the groups too
        if isinstance(aca, LazyView):
            groups = aca["groups"]
            acaname = aca["name"].decode("ascii")
        else:
            assert isinstance(aca, Academy)
            groups = aca.getgroups()
            acaname = aca.name.decode("ascii")
        if course is None:
            pass
        elif isinstance(course, LazyView):
            coursename = course["name"].decode("ascii")
        else:
            assert isinstance(course, Course)
            coursename = course.name.decode("ascii")
        ## second check for explicitly revoked privilege
        if course is None:
            if self.revokedPermission("akademie_write_%s" % acaname):
                return False
        else:
            if self.revokedPermission("kurs_write_%s_%s" %
                                      (acaname, coursename)):
                return False
            if self.revokedPermission("akademie_write_%s" % acaname) and \
               not self.hasPermission("kurs_write_%s_%s" %
                                      (acaname, coursename)):
                return False
        ## now we are done with revoked permissions and can continue
        ## third check group level privileges
        for g in groups:
            if self.hasPermission("gruppe_write_%s" % g):
                return True
        ## fourth check the academy level priveleges
        if self.hasPermission("akademie_write_%s" % acaname):
            return True
        if course is None:
            ## no write access to the academy
            return False
        ## at this point we ask for a write privelege of a specific course
        return self.hasPermission("kurs_write_%s_%s" % (acaname, coursename))

    def allowedMeta(self, aca: typing.Union[Academy, LazyView]) -> bool:
        ## first check global priveleges
        if self.hasPermission("df_meta") or self.isSuperAdmin():
            return True
        ## now we need to resolve aca
        ## a bit care has to be taken since we need the groups too
        if isinstance(aca, LazyView):
            groups = aca["groups"]
            acaname = aca["name"].decode("ascii")
        else:
            assert isinstance(aca, Academy)
            groups = aca.getgroups()
            acaname = aca.name.decode("ascii")
        ## second check for explicitly revoked privilege
        if self.revokedPermission("akademie_meta_%s" % acaname):
            return False
        ## now we are done with revoked permissions and can continue
        ## third check group level privileges
        for g in groups:
            if self.hasPermission("gruppe_meta_%s" % g):
                return True
        ## fourth check the academy level priveleges
        return self.hasPermission("akademie_meta_%s" % acaname)

    def mayExport(self, aca: typing.Union[Academy, LazyView]) -> bool:
        assert isinstance(aca, Academy) or isinstance(aca, LazyView)
        ## superadmin is allowed to do everything
        if self.isSuperAdmin():
            return True
        ## we require the corresponding read privelege
        ## akademie_view_* shall not be enough, hence we demand recursive
        if not self.allowedRead(aca, recursive = True):
            return False
        ## now we have to check the export privelege
        return self.hasPermission("df_export")

    def mayCreate(self) -> bool:
        return self.hasPermission("df_create") or self.isSuperAdmin()

    def allowedList(self, groupname: str) -> bool:
        assert isinstance(groupname, str)
        return self.isSuperAdmin() or self.hasPermission("df_show") or \
            self.hasPermission("gruppe_show_%s" % groupname)

    def isAdmin(self) -> bool:
        return self.isSuperAdmin() or self.hasPermission("df_admin")

    def isSuperAdmin(self) -> bool:
        return self.hasPermission("df_superadmin")

    def defaultGroup(self) -> str:
        """Return the default group of a user. This is the first part (separated by
        underscore) of the status.
        """
        ret = self.status.split('_')[0]
        return ret

class UserDB:
    """
    Class for the user database

    @ivar db: dictionary containing (username, User object) pairs
    @ivar storage: storage.CachingStorage object holding the userdb
    @ivar timestamp: time of last update, this is compared to the mtime of
        the CachingStorage
    """
    def __init__(self, storage: CachingStorage) -> None:
        self.db: typing.Dict[str, User] = dict()
        self.storage = storage
        self.timestamp = epoch

    def addUser(self, name: str, status: str, password: str,
                permissions: typing.Dict[str, bool]):
        """
        add a user to the database in memory

        @param permissions: dictionary of permissions
        """
        assert isinstance(name, str)
        assert isinstance(status, str)
        assert isinstance(password, str)
        assert all(isinstance(key, str) and isinstance(value, bool)
                   for key, value in permissions.items())
        if name in self.db:
            return False
        self.db[name] = User(name, status, password, permissions)
        return True

    def checkLogin(self, name: str, password: str):
        """
        @returns: True if name and password match an existing user, False otherwise
        """
        assert isinstance(name, str)
        assert isinstance(password, str)
        try:
            return self.db[name].password == password
        except KeyError:
            return False

    def load(self) -> None:
        """
        Load the user database from disk.

        This erases all in-memory changes.
        """
        ## if nothing is changed return
        if self.storage.timestamp() <= self.timestamp:
            return
        config = configparser.ConfigParser()
        content = self.storage.content().decode("utf8")
        ## update time, since we read the new content
        self.timestamp = self.storage.cachedtime
        config.read_string(content)
        ## clear after we read the new config, better safe than sorry
        self.db.clear()
        for name in config.sections():
            permissions = dict((perm.strip().split(' ')[0],
                                strtobool(perm.strip().split(' ')[1]))
                for perm in config.get(name, 'permissions').split(','))
            self.addUser(name, config.get(name, 'status'),
                         config.get(name, 'password'), permissions)
