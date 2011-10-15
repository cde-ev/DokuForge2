
import os
import storage
import course

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
            self.path = path
        self.courses = [course.Course(self.path + '/' + y) for y in [x for x in os.listdir(self.path) if 'course' in x]]
    def gettitle(self):
        s=storage.Storage(self.path,"title")
        return s.content()
    def getgroups(self):
        s=storage.Storage(self.path,"groups")
        return s.content().split(' ')

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
