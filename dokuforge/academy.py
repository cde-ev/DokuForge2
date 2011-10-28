
import os
import re
import operator

from dokuforge.course import Course
from dokuforge.storagedir import StorageDir
import dokuforge.common as common
from dokuforge.common import CheckError

class Academy(StorageDir):
    """
    Backend for manipulating the file structres related to an academy

    It is characterised by the path of a directory. The directory should
    contain the following files. All directories within this directory are
    assumed to contain a course.

    title,v    The title of this display name of this academy
    groups,v   The groups in which this academy is a member
    """
    def __init__(self, obj):
        """
        @param obj: either a path or an Academy object
        @type obj: str or Academy
        """
        StorageDir.__init__(self, obj)

    def getgroups(self):
        """
        loads the current groups from disk

        @returns: the groups of which this academy is a member
        @rtype: [unicode]
        """
        return self.getcontent("groups").decode("utf8").split()

    def viewCourses(self):
        """
        @returns: list of Course.view dicts for all courses of this academy
        """
        return [course.view() for course in self.listCourses()]

    def listCourses(self):
        """
        @returns: list of Course object; all courses of this academy
        """
        ret = (os.path.join(self.path, entry)
               for entry in os.listdir(self.path))
        ret = filter(os.path.isdir, ret)
        ret = map(Course, ret)
        ret = list(ret)
        ret.sort(key=operator.attrgetter('name'))
        return ret

    def getCourse(self, coursename):
        """
        find a course of this academy to a given name

        @param coursename: internal name of course
        @type coursename: unicode
        @returns: Course object for course with name coursename
        """
        assert isinstance(coursename, unicode)
        coursename = coursename.encode("utf8")
        if re.match('^[-a-zA-Z0-9]{1,200}$', coursename) is None:
            return None
        finalpath = os.path.join(self.path, coursename)
        if not os.path.isdir(finalpath):
            return None
        return Course(finalpath)

    def setgroups(self, groups):
        """
        Set the groups of this academy to determine when to display it

        @param groups: groups to set
        @type groups: list of unicode
        """
        assert all(isinstance(group, unicode) for group in groups)
        content = u" ".join(groups)
        self.getstorage("groups").store(content.encode("utf8"))

    def createCourse(self, name, title):
        """
        create a new course

        @param name: internal name of the course
        @param title: displayed name of the course
        @type name: str (restricted char-set)
        @type title: unicode
        """
        assert isinstance(name, unicode)
        assert isinstance(title, unicode)
        name = name.encode("utf8")
        try:
            common.validateInternalName(name)
            common.validateNonExistence(self.path, name)
            common.validateTitle(title)
        except CheckError:
            return False
        Course(os.path.join(self.path, name)).settitle(title)
        return True

    def view(self, extrafunctions=dict()):
        """
        @rtype: LazyView
        @returns: a mapping providing the keys: name(str), title(unicode),
            courses([Course.view()]), groups([unicode])
        """
        functions = dict(courses=self.viewCourses,
                         groups=self.getgroups)
        functions.update(extrafunctions)
        return StorageDir.view(self, functions)
