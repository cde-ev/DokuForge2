
import os
import storage
import course
import re
import operator
from course import Course, CourseLite

class AcademyLite:
    """
    Backend for viewing the file structres related to an academy

    A detailed description can be found with the class Academy.
    """

    def __init__(self, obj):
        """
        @param obj: either a path or an Academy object
        @type obj: str or Academy object or AcademyLite object
        """
        if isinstance(obj, AcademyLite):
            self.path = obj.path
        else:
            assert isinstance(obj, str)
            self.path = obj

    @property
    def name(self):
        """
        internal name of academy
        """
        return os.path.basename(self.path)

    def gettitle(self):
        """
        loads the current title from disk

        @returns: the display name of this academy
        @rtype: unicode
        """
        return storage.Storage(self.path, "title").content().decode("utf8")

    def getgroups(self):
        """
        loads the current groups from disk

        @returns: the groups of which this academy is a member
        @rtype: [unicode]
        """
        return storage.Storage(self.path, "groups").content().decode("utf8").split()

    def listCoursesLite(self):
        """
        @returns: list of CourseLite object; all courses of this academy
        """
        ret = (os.path.join(self.path, entry)
               for entry in os.listdir(self.path))
        ret = filter(os.path.isdir, ret)
        ret = map(course.CourseLite, ret)
        ret = list(ret)
        ret.sort(key=operator.attrgetter('name'))
        return ret

    def getCourseLite(self, coursename):
        """
        find a course of this academy to a given name

        @param coursename: internal name of course
        @type coursename: unicode
        @returns: CourseLite object for course with name coursename
        """
        assert isinstance(coursename, unicode)
        coursename = coursename.encode("utf8")
        if re.match('^[-a-zA-Z0-9]{1,200}$', coursename) is None:
            return None
        finalpath = os.path.join(self.path,coursename)
        if not os.path.isdir(finalpath):
            return None
        return CourseLite(finalpath)


class Academy(AcademyLite):
    """
    Backend for manipulating the file structres related to a course

    It is characterised by the path of a directory. The directory should
    contain the following files. All directories within this directory are
    assumed to contain a course.

    title,v    The title of this display name of this academy
    groups,v   The groups in which this academy is a member
    """
    def __init__(self, obj):
        """
        @param obj: either a path or an Academy object
        @type obj: str or Academy object or AcademyLite object
        """
        AcademyLite.__init__(self, obj)

    def settitle(self, title):
        """
        Set the title of this academy

        @param title: display name of the academy
        @type title: unicode
        """
        assert isinstance(title, unicode)
        if title == u"":
            return False
        storage.Storage(self.path,"title").store(title.encode("utf8"))
        return True

    def setgroups(self, groups):
        """
        Set the groups of this academy to determine when to display it

        @param groups: groups to set
        @type groups: list of unicode
        """
        assert all(isinstance(group, unicode) for group in groups)
        content = u" ".join(groups)
        storage.Storage(self.path, "groups").store(content.encode("utf8"))

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
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            return False
        if title == u"":
            return False
        if os.path.exists(os.path.join(self.path, name)):
            return False
        course.Course(os.path.join(self.path, name)).settitle(title)
        return True

    def listCourses(self):
        """
        @returns: list of Course object; all courses of this academy
        """
        return list(map(course.Course, self.listCoursesLite()))

    def getCourse(self, coursename):
        """
        find a course of this academy to a given name

        @param coursename: internal name of course
        @type coursename: unicode
        @returns: Course object for course with name coursename
        """
        assert isinstance(coursename, unicode)
        litecourse = self.getCourseLite(coursename)
        if litecourse is None:
            return None
        return Course(litecourse)

