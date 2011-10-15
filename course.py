
import os

class Course:
    """
    Backend for manipulating the file structres related to a course

    A course is described by a directory. This directory may contain, among
    other things, the following files; with each rcs file, the associated file
    and locks as described in L{Storage} can be present as well.

    index,v    List of internal page numbers, in order of appearence

    pageN,v    The page with internal number N
    """

    def __init__(self,path):
        """
        @param: the directory for storing the course; each course must have
                its own directory, and only course data should be stored in this directory
        """
        self.path = path
        os.makedirs(self.path)
