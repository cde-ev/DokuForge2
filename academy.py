
import os
import storage
import course
import re
import copy

class AcademyLite:
    """
    ...
    """

    def __init__(self, obj):
        """
        """
        if isinstance(obj, AcademyLite):
            self.path = obj.path
        else:
            self.path = obj
        self.courses = [course.Course(os.path.join(self.path, y)) for y in
                        [x for x in os.listdir(self.path) if 'course' in x]]
    @property
    def name(self):
        return os.path.basename(self.path)
    def gettitle(self):
        s=storage.Storage(self.path,"title")
        return s.content()
    def getgroups(self):
        s=storage.Storage(self.path,"groups")
        return s.content().split(' ')
    def listCoursesLite(self):
        candidates = os.listdir(self.path)
        final = copy.deepcopy(candidates)
        for x in candidates:
            if not os.path.isdir(os.path.join(self.path, x)):
                final.remove(x)
        return [course.CourseLite(os.path.join(self.path, x)) for x in final]

class Academy(AcademyLite):
    def __init__(self, obj):
        """
        """
        AcademyLite.__init__(self, obj)
    def settitle(self, title):
        """
        Set the title of this academy
        """
        s=storage.Storage(self.path,"title")
        s.store(title)
    def setgroups(self, groups):
        """
        Set the groups of this academy to determine when to display it
        """
        s=storage.Storage(self.path,"groups")
        s.store(' '.join(x for x in groups))
    def createCourse(self, name, title):
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            return False
        c = course.Course(os.path.join(self.path, name))
        c.settitle(title)
    def listCourses(self):
        candidates = os.listdir(self.path)
        final = copy.deepcopy(candidates)
        for x in candidates:
            if not os.isdir(os.path.join(self.path, x)):
                final.remove(x)
        return [course.Course(os.path.join(self.path, x)) for x in final]
