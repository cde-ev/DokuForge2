
import os
import storage
import course
import re
import copy
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

        @returns: str, the display name of this academy
        """
        s=storage.Storage(self.path,"title")
        return s.content()

    def getgroups(self):
        """
        loads the current groups from disk

        @returns: list of str, the groups of which this academy is a member
        """
        s=storage.Storage(self.path,"groups")
        return s.content().split(' ')

    def listCoursesLite(self):
        """
        @returns: list of CourseLite object; all courses of this academy
        """
        candidates = os.listdir(self.path)
        final = copy.deepcopy(candidates)
        for x in candidates:
            if not os.path.isdir(os.path.join(self.path, x)):
                final.remove(x)
        return [course.CourseLite(os.path.join(self.path, x)) for x in final]

    def getCourseLite(self, coursename):
        """
        find a course of this academy to a given name

        @param coursename: internal name of course
        @type coursename: str (restricted char-set)
        @returns: CourseLite object for course with name coursename
        """
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
        @type title: str
        """
        s=storage.Storage(self.path,"title")
        s.store(title)

    def setgroups(self, groups):
        """
        Set the groups of this academy to determine when to display it

        @params groups: groups to set
        @type groups: list of str
        """
        s=storage.Storage(self.path,"groups")
        s.store(' '.join(x for x in groups))

    def createCourse(self, name, title):
        """
        create a new course

        @param name: internal name of the course
        @param title: displayed name of the course
        @type name: str (restricted char-set)
        @type title: str
        """
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            return False
        c = course.Course(os.path.join(self.path, name))
        c.settitle(title)

    def listCourses(self):
        """
        @returns: list of Course object; all courses of this academy
        """
        candidates = os.listdir(self.path)
        final = copy.deepcopy(candidates)
        for x in candidates:
            if not os.path.isdir(os.path.join(self.path, x)):
                final.remove(x)
        return [course.Course(os.path.join(self.path, x)) for x in final]

    def getCourse(self,coursename):
        """
        find a course of this academy to a given name

        @param coursename: internal name of course
        @type coursename: str (restricted char-set)
        @returns: Course object for course with name coursename
        """
        litecourse = self.getCourseLite(coursename)
        if litecourse is None:
            return None
        return Course(litecourse)

