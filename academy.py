
import os
import storage
import course
import re
import operator
from course import Course
import view

class Academy:
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
        @type obj: str or Academy
        """
        if isinstance(obj, Academy):
            self.path = obj.path
        else:
            assert isinstance(obj, str)
            self.path = obj

    def getstorage(self, filename):
        """
        @type filename: str
        @param filename: passed to Storage as second param
        @rtype: Storage
        @returns: a Storage build from self.path and filename
        """
        assert isinstance(filename, str)
        return storage.Storage(self.path, filename)

    def getcontent(self, filename):
        """
        @type filename: str
        @param filename: passed to Storage as second param
        @rtype: str
        @returns: the content of the Storage buil from self.path and filename
        """
        return self.getstorage(filename).content()

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
        return self.getcontent("title").decode("utf8")

    def getgroups(self):
        """
        loads the current groups from disk

        @returns: the groups of which this academy is a member
        @rtype: [unicode]
        """
        return self.getcontent("groups").decode("utf8").split()

    def viewCourses(self):
        return [course.view() for course in self.listCourses()]

    def listCourses(self):
        """
        @returns: list of Course object; all courses of this academy
        """
        ret = (os.path.join(self.path, entry)
               for entry in os.listdir(self.path))
        ret = filter(os.path.isdir, ret)
        ret = map(course.Course, ret)
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
        finalpath = os.path.join(self.path,coursename)
        if not os.path.isdir(finalpath):
            return None
        return Course(finalpath)


    def settitle(self, title):
        """
        Set the title of this academy

        @param title: display name of the academy
        @type title: unicode
        """
        assert isinstance(title, unicode)
        self.getstorage("title").store(title.encode("utf8"))

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
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            return False
        if os.path.exists(os.path.join(self.path, name)):
            return False
        course.Course(os.path.join(self.path, name)).settitle(title)
        return True

    def view(self):
        """
        @rtype: LazyView
        @returns: a mapping providing the keys: name(str), title(unicode),
            courses([Course.view()]), groups([unicode])
        """
        return view.LazyView(dict(
            name=lambda:self.name,
            title=self.gettitle,
            courses=self.viewCourses,
            groups=self.getgroups))
