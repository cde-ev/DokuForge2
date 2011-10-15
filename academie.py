
import os
import storage

class Academy:
    """
    ...
    """

    def __init__(self, path):
        """
        @param: the directory for storing the academy; each academy must have
                its own directory.
        """
        self.path = path
        try:
            os.makedirs(self.path)
        except OSError:
            pass
        self.courses = []
    def settitle(self,title):
        """
        Set the title of this course
        """
        s=storage.Storage(self.path,"title")
        s.store(title)
    def gettitle(self):
        s=storage.Storage(self.path,"title")
        return s.content()
    def load(self):
        print os.listdir(self.path)
