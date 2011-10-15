import os
from storage import Storage

class Course:
    """
    Backend for manipulating the file structres related to a course

    A course is described by a directory. This directory may contain, among
    other things, the following files; with each rcs file, the associated file
    and locks as described in L{Storage} can be present as well.

    Index,v    List of internal page numbers, in order of appearence
               Each line contains the internal page number, followed by a space,
               optionally followed by internal blob-numbers associated with page.

    pageN,v    The page with internal number N

    blobN,v    The blob with the internal number N

    nextpage,v contains the number of the next available page
    nextblob,v contains the number of the next available blob
    """

    def __init__(self,path):
        """
        @param: the directory for storing the course; each course must have
                its own directory, and only course data should be stored in this directory
        """
        self.path = path
        try:
            os.makedirs(self.path)
        except os.error:
            pass

    def nextpage(self,havelock=False):
        """
        internal function: return the number of the next available page, but don't do anything
        """
        s = Storage(self.path,"nextpage")
        vs = s.content(havelock=havelock)
        if vs=='':
            vs='0'
        return int(vs)

    def newpage(self,havelock=False):
        """
        create a new page in this course and return its internal number
        """
        index = Storage(self.path,"Index")
        nextpagestore = Storage(self.path,"nextpage")
        index.getlock()
        nextpagestore.getlock()
        try:
            newnumber = self.nextpage(havelock=True)
            nextpagestore.store("%d" % (newnumber+1),havelock=True)
            indexcontents = index.content(havelock=True)
            indexcontents += "%s\n" % newnumber
            index.store(indexcontents,havelock=True)
        finally:
            nextpagestore.releaselock()
            index.releaselock()
        return newnumber

    def listpages(self,havelock=False):
        """
        return a list of the available page numbers in correct order
        """
        indexstore = Storage(self.path,"Index")
        index = indexstore.content(havelock=havelock)
        lines = index.split('\n')
        lines.pop()
        return [int(line.split()[0]) for line in lines]

    def showpage(self,number):
        """
        Show the contents of a page
        
        @param number: the internal number of that page
        """
        page = Storage(self.path,"page%d" % number)
        return page.content()

    def delpage(self,number):
        """
        Delete a page

        @param number: the internal page number
        """
        indexstore = Storage(self.path,"Index")
        indexstore.getlock()
        try:
            index = indexstore.content(havelock=True)
            lines = index.split('\n')
            lines.pop()
            newlines = []
            for line in lines:
                if int(line.split()[0])!=number:
                    newlines.append(line)
            newindex="\n".join(newlines) + "\n"
            indexstore.store(newindex,havelock=True)
        finally:
            indexstore.releaselock()


    def editpage(self,number):
        """
        Start editing a page; 

        @param number: the internal page number
        @returns a pair of an opaque version string and the contents of this page
        """
        page = Storage(self.path,"page%d" % number)
        return page.startedit()

    def savepage(self,number,version, newcontent,user=None):
        """
        Finish editing a page

        @param number: the internal page number
        @param version: the opaque version string, as obtained from edit page
        @param newcontent: the new content of the page, based on editing the said version
        @param user: the df-login name of the user to carried out the edit

        @returns: a triple (ok,newversion,mergedcontent) where ok is a boolean indicating
                  whether no confilct has occured and (newversion,mergedcontent) a pair
                  for further editing that can be  handled as if obtained from editpage
        """
        page = Storage(self.path,"page%d" % number)
        return page.endedit(version,newcontent,user=user)
