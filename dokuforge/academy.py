
import os
import operator
import datetime

import werkzeug.exceptions

from dokuforge.course import Course, Valuation
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
    def __init__(self, obj, listAllGroups):
        """
        @param obj: either a path or an Academy object
        @type obj: str or Academy
        """
        StorageDir.__init__(self, obj)
        self.listAllGroups = listAllGroups

    def getgroups(self):
        """
        loads the current groups from disk, list version.

        @returns: the groups of which this academy is a member
        @rtype: [unicode]
        """
        return self.getcontent("groups").decode("utf8").split()

    def getgroupsstring(self):
        """
        loads the current groups from disk, string version.

        @returns: the groups of which this academy is a member
        @rtype: unicode
        """
        return self.getcontent("groups").decode("utf8")

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
        find a course of this academy to a given name. If none is found
        raise a werkzeug.exceptions.NotFound.

        @param coursename: internal name of course
        @type coursename: unicode
        @returns: Course object for course with name coursename
        @raises werkzeug.exceptions.NotFound: if the course does not exist
        """
        assert isinstance(coursename, unicode)
        coursename = coursename.encode("utf8")
        try:
            common.validateInternalName(coursename)
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
        self.getstorage("groups").store(content.encode("utf8"))

    def createCourse(self, name, title):
        """
        create a new course. If the user input is malformed raise a check
        error.

        @param name: internal name of the course
        @param title: displayed name of the course
        @type name: str (restricted char-set)
        @type title: unicode
        @raises CheckError:
        """
        assert isinstance(name, unicode)
        assert isinstance(title, unicode)
        name = name.encode("utf8")
        common.validateInternalName(name)
        common.validateNonExistence(self.path, name)
        common.validateTitle(title)
        c = Course(os.path.join(self.path, name))
        c.settitle(title)
        c.setlivingstate(True)

    def lastchange(self):
        lastchange = {'author': u'unkown', 'revision' : u'?', 'date' : u'1970/01/01 00:00:00'}
        for c in self.listCourses():
            info = c.lastchange()
            date =  datetime.datetime.strptime(info['date'], "%Y/%m/%d %H:%M:%S")
            compare = datetime.datetime.strptime(lastchange['date'], "%Y/%m/%d %H:%M:%S")
            if date > compare:
                lastchange = info
        return lastchange

    def estimate(self):
        estimate = Valuation()
        for c in self.listCourses():
            estimate += c.estimate()
        return estimate

    def view(self, extrafunctions=dict()):
        """
        @rtype: LazyView
        @returns: a mapping providing the keys: name(str), title(unicode),
            courses([Course.view()]), groups([unicode])
        """
        functions = dict(courses=self.viewCourses,
                         groups=self.getgroups,
                         lastchange=self.lastchange,
                         estimate=self.estimate)
        functions.update(extrafunctions)
        return StorageDir.view(self, functions)
