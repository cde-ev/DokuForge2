
import os

class Academy:
    """
    ...
    """

    def __init__(self, path, title, courselist=[]):
        """
        @param path: the directory for storing the academy; each academy must
                have its own directory.
        """
        self.path = path
        try:
            os.makedirs(self.path)
        except OSError:
            pass
        self.courselist = courselist
        self.title = title
