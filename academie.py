
import os

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
        self.title = ""
        self.courses = []
    def settitle(self, title):
        f = open(self.path + '/title', 'w')
        f.write(title)
        f.close()
    def load(self):
        print os.listdir(self.path)
