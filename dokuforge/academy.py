
import os
import operator
import datetime
import typing

import werkzeug.exceptions

from dokuforge.course import Course
from dokuforge.storagedir import StorageDir
import dokuforge.common as common
from dokuforge.common import CheckError
from dokuforge.view import LazyView
try:
    from dokuforge.versioninfo import commitid
except ImportError:
    commitid = "unknown"

class Academy(StorageDir):
    """
    Backend for manipulating the file structres related to an academy

    It is characterised by the path of a directory. The directory should
    contain the following files. All directories within this directory are
    assumed to contain a course.

    title,v    The title of this display name of this academy
    groups,v   The groups in which this academy is a member
    """
    def __init__(self, obj: typing.Union[bytes, "Academy"],
                 listAllGroups) -> None:
        """
        @param obj: either a path or an Academy object
        """
        StorageDir.__init__(self, obj)
        self.listAllGroups = listAllGroups

    def getgroups(self) -> typing.List[str]:
        """
        loads the current groups from disk, list version.

        @returns: the groups of which this academy is a member
        """
        return self.getcontent(b"groups").decode("utf8").split()

    def getgroupsstring(self) -> str:
        """
        loads the current groups from disk, string version.

        @returns: the groups of which this academy is a member
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
        paths = (os.path.join(self.path, entry)
                 for entry in os.listdir(self.path))
        ret = [Course(p) for p in paths if os.path.isdir(p)]
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

    def getCourse(self, coursename: str):
        """
        find a course of this academy to a given name. The course may be
        deleted. If none is found raise a werkzeug.exceptions.NotFound.

        @param coursename: internal name of course
        @returns: Course object for course with name coursename
        @raises werkzeug.exceptions.NotFound: if the course does not exist
        """
        assert isinstance(coursename, str)
        try:
            common.validateInternalName(coursename)
            coursenameb = coursename.encode("utf8")
            common.validateExistence(self.path, coursenameb)
        except CheckError:
            raise werkzeug.exceptions.NotFound()
        return Course(os.path.join(self.path, coursenameb))

    def setgroups(self, groups: typing.List[str]) -> None:
        """
        Set the groups of this academy to determine when to display it. If
        the input is malformed raise a CheckError.

        @param groups: groups to set
        """
        if isinstance(groups, str):
            groups = groups.split()
        assert all(isinstance(group, str) for group in groups)
        common.validateGroups(groups, self.listAllGroups())
        content = " ".join(groups)
        self.getstorage(b"groups").store(content.encode("utf8"))

    def createCourse(self, name: str, title: str) -> None:
        """
        create a new course. If the user input is malformed raise a check
        error.

        @param name: internal name of the course
        @param title: displayed name of the course
        @type name: str (restricted char-set)
        @raises CheckError:
        """
        assert isinstance(name, str)
        assert isinstance(title, str)
        common.validateInternalName(name)
        nameb = name.encode("utf8")
        common.validateNonExistence(self.path, nameb)
        common.validateTitle(title)
        Course(os.path.join(self.path, nameb)).settitle(title)

    def lastchange(self):
        return common.findlastchange([c.lastchange() for c in self.listCourses()])

    def timestamp(self):
        return max([c.timestamp() for c in self.listCourses()] + [-1])

    def view(self, extrafunctions=dict()) -> LazyView:
        """
        @returns: a mapping providing the keys: name(bytes), title(str),
            courses([Course.view()]), groups([str])
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
        timeStampNow.replace(tzinfo=datetime.timezone.utc)
        yield tarwriter.addChunk(b"WARNING",
("""The precise semantics of the exporter is still
subject to discussion and may change in future versions.
If you think you might need to reproduce an export with the
same exporter semantics, keep the following version string
for your reference

%s
""" % commitid).encode("ascii"),timeStampNow)
        if static is not None:
            for chunk in tarwriter.addDirChunk(b"", static, excludes=[b".svn"]):
                yield chunk
        contents = ""
        for course in self.listCourses():
            contents += "\\include{%s/chap}\n" % course.name.decode("ascii")
            for chunk in course.texExportIterator(tarwriter):
                yield chunk
        yield tarwriter.addChunk(b"contents.tex",
                                 contents.encode("utf8"),
                                 timeStampNow)
