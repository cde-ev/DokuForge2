
import os
import operator
import datetime

import werkzeug.exceptions

from dokuforge.course import Course
from dokuforge.storagedir import StorageDir
import dokuforge.common as common
from dokuforge.common import CheckError
try:
    from dokuforge.versioninfo import commitid
except ImportError:
    commitid = u"unknown"

try:
    unicode
except NameError:
    unicode = str

class Academy(StorageDir):
    """
    Backend for manipulating the file structres related to an academy

    It is characterised by the path of a directory. The directory should
    contain the following files. All directories within this directory are
    assumed to contain a course.

    title,v    The title of this display name of this academy
    groups,v   The groups in which this academy is a member
    """
    def __init__(self, obj, listAllGroups):
        """
        @param obj: either a path or an Academy object
        @type obj: bytes or Academy
        """
        StorageDir.__init__(self, obj)
        self.listAllGroups = listAllGroups

    def getgroups(self):
        """
        loads the current groups from disk, list version.

        @returns: the groups of which this academy is a member
        @rtype: [unicode]
        """
        return self.getcontent(b"groups").decode("utf8").split()

    def getgroupsstring(self):
        """
        loads the current groups from disk, string version.

        @returns: the groups of which this academy is a member
        @rtype: unicode
        """
        return self.getcontent(b"groups").decode("utf8")

    def viewCourses(self):
        """
        @returns: list of Course.view dicts for all non-deleted courses of this academy
        """
        return [course.view() for course in self.listCourses()]

    def viewDeadCourses(self):
        """
        @returns: list of Course.view dicts for all deleted courses of this academy
        """
        return [course.view() for course in self.listDeadCourses()]

    def listAllCourses(self):
        """
        @returns: list of Course object; all courses of this academy, including
            deleted ones.
        """
        ret = (os.path.join(self.path, entry)
               for entry in os.listdir(self.path))
        ret = filter(os.path.isdir, ret)
        ret = map(Course, ret)
        ret = list(ret)
        ret.sort(key=operator.attrgetter('name'))
        return ret

    def listCourses(self):
        """
        @returns: list of Course object; all non-deleted courses of this academy
        """
        return [c for c in self.listAllCourses() if not c.isDeleted]

    def listDeadCourses(self):
        """
        @returns: list of Course object; all deleted courses of this academy
        """
        return [c for c in self.listAllCourses() if c.isDeleted]

    def getCourse(self, coursename):
        """
        find a course of this academy to a given name. The course may be
        deleted. If none is found raise a werkzeug.exceptions.NotFound.

        @param coursename: internal name of course
        @type coursename: unicode
        @returns: Course object for course with name coursename
        @raises werkzeug.exceptions.NotFound: if the course does not exist
        """
        assert isinstance(coursename, unicode)
        try:
            common.validateInternalName(coursename)
            coursename = coursename.encode("utf8")
            common.validateExistence(self.path, coursename)
        except CheckError:
            raise werkzeug.exceptions.NotFound()
        return Course(os.path.join(self.path, coursename))

    def setgroups(self, groups):
        """
        Set the groups of this academy to determine when to display it. If
        the input is malformed raise a CheckError.

        @param groups: groups to set
        @type groups: list of unicode
        """
        if isinstance(groups, unicode):
            groups = groups.split()
        assert all(isinstance(group, unicode) for group in groups)
        common.validateGroups(groups, self.listAllGroups())
        content = u" ".join(groups)
        self.getstorage(b"groups").store(content.encode("utf8"))

    def createCourse(self, name, title):
        """
        create a new course. If the user input is malformed raise a check
        error.

        @param name: internal name of the course
        @param title: displayed name of the course
        @type name: unicode (restricted char-set)
        @type title: unicode
        @raises CheckError:
        """
        assert isinstance(name, unicode)
        assert isinstance(title, unicode)
        common.validateInternalName(name)
        name = name.encode("utf8")
        common.validateNonExistence(self.path, name)
        common.validateTitle(title)
        Course(os.path.join(self.path, name)).settitle(title)

    def lastchange(self):
        return common.findlastchange([c.lastchange() for c in self.listCourses()])

    def timestamp(self):
        return max([c.timestamp() for c in self.listCourses()] + [-1])

    def view(self, extrafunctions=dict()):
        """
        @rtype: LazyView
        @returns: a mapping providing the keys: name(bytes), title(unicode),
            courses([Course.view()]), groups([unicode])
        """
        functions = dict(courses=self.viewCourses,
                         deadcourses=self.viewDeadCourses,
                         groups=self.getgroups,
                         lastchange=self.lastchange,
                         timestamp=self.timestamp)
        functions.update(extrafunctions)
        return StorageDir.view(self, functions)

    def texExportIterator(self, tarwriter, static=None):
        """
        yield a tar archive containing the tex-export of the academy.
        """
        timeStampNow = datetime.datetime.utcnow()
        timeStampNow.replace(tzinfo=common.utc)
        yield tarwriter.addChunk(b"WARNING",
(u"""The precise semantics of the exporter is still
subject to discussion and may change in future versions.
If you think you might need to reproduce an export with the
same exporter semantics, keep the following version string
for your reference

%s
""" % commitid).encode("ascii"),timeStampNow)
        if static is not None:
            for chunk in tarwriter.addDirChunk(b"", static, excludes=[b".svn"]):
                yield chunk
        contents = u""
        for course in self.listCourses():
            contents += u"\\include{%s/chap}\n" % course.name.decode("ascii")
            for chunk in course.texExportIterator(tarwriter):
                yield chunk
        yield tarwriter.addChunk(b"contents.tex",
                                 contents.encode("utf8"),
                                 timeStampNow)
