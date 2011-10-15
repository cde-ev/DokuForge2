import os
from storage import Storage

class CourseLite:
    """
    Backend for viewing the file structres related to a course

    A detailed description can be found with the class Course.
    """
    def __init__(self,obj):
        """
        """
        if isinstance(obj, CourseLite):
            self.path = obj.path
        else:
            self.path = obj
        try:
            os.makedirs(self.path)
        except os.error:
            pass

    @property
    def name(self):
        return os.path.basename(self.path)

    def gettitle(self):
        s=Storage(self.path,"title")
        return s.content()

    def nextpage(self,havelock=False):
        """
        internal function: return the number of the next available page, but don't do anything
        """
        s = Storage(self.path,"nextpage")
        vs = s.content(havelock=havelock)
        if vs=='':
            vs='0'
        return int(vs)

    def listpages(self,havelock=False):
        """
        return a list of the available page numbers in correct order
        """
        indexstore = Storage(self.path,"Index")
        index = indexstore.content(havelock=havelock)
        lines = index.splitlines()
        return [int(line.split()[0]) for line in lines]

    def showpage(self,number):
        """
        Show the contents of a page

        @param number: the internal number of that page
        """
        page = Storage(self.path,"page%d" % number)
        return page.content()


class Course(CourseLite):
    """
    Backend for manipulating the file structres related to a course

    A course is described by a directory. This directory may contain, among
    other things, the following files; with each rcs file, the associated file
    and locks as described in L{Storage} can be present as well.

    title,v    The title of this course (as to be printed)

    Index,v    List of internal page numbers, in order of appearence
               Each line contains the internal page number, followed by a space,
               optionally followed by internal blob-numbers associated with page.

    pageN,v    The page with internal number N

    blobN,v    The blob with the internal number N

    nextpage,v contains the number of the next available page
    nextblob,v contains the number of the next available blob
    """
    def __init__(self,obj):
        """
        """
        CourseLite.__init__(self, obj)

    def settitle(self,title):
        """
        Set the title of this course
        """
        s=Storage(self.path,"title")
        s.store(title)

    def newpage(self):
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

    def delpage(self,number):
        """
        Delete a page

        @param number: the internal page number
        """
        indexstore = Storage(self.path,"Index")
        indexstore.getlock()
        try:
            index = indexstore.content(havelock=True)
            lines = index.splitlines()
            newlines = []
            for line in lines:
                if int(line.split()[0])!=number:
                    newlines.append(line)
            newindex="\n".join(newlines) + "\n"
            indexstore.store(newindex,havelock=True)
        finally:
            indexstore.releaselock()

    def swappages(self,position):
        """
        the page at the given current position with its predecessor
        """
        indexstore = Storage(self.path,"Index")
        indexstore.getlock()
        try:
            index = indexstore.content(havelock=True)
            lines = index.splitlines()
            if position<len and position>0:
                tmp =lines[position-1]
                lines[position-1]=lines[position]
                lines[position]=tmp
            newindex="\n".join(lines) + "\n"
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

    def nextblob(self,havelock=False):
        """
        internal function: return the number of the next available blob, but don't do anything
        """
        s = Storage(self.path,"nextblob")
        vs = s.content(havelock=havelock)
        if vs=='':
            vs='0'
        return int(vs)

    def attachblob(self,number,data,comment="unknown blob",user=None):
        """
        Attach a blob to a page

        @param number: the internal number of the page
        @param title: a short description, e.g., the original file name
        @param comment: a human readable description, e.g., the caption to be added to this figure 
        """
        indexstore = Storage(self.path,"Index")
        nextblobstore = Storage(self.path,"nextpage")
        indexstore.getlock()
        nextblobstore.getlock()

        try:
            newnumber = self.nextpage(havelock=True)
            nextblobstore.store("%d" % (newnumber+1),havelock=True)
            index = indexstore.content()
            lines = index.splitlines()
            for i in range(len(lines)):
                if int(lines[i].split()[0])==number:
                    lines[i] += " %d" % newnumber
            newindex="\n".join(lines) + "\n"
            indexstore.store(newindex,havelock=True)
        finally:
            nextblobstore.releaselock()
            indexstore.releaselock()


        blob = Storage(self.path,"blob%d" % newnumber)
        blob.store(data,user=user,message=comment)

    def listblobs(self,number):
        """
        return a list of the blobs associated with the given page

        @param number: the internal page number
        """
        indexstore = Storage(self.path,"Index")
        index = indexstore.content()
        lines = index.splitlines()
        for line in lines:
            entries=line.split()
            if int(entries[0]) == number:
                entries.pop(0)
                return [int(x) for x in entries]
        return []

    def getblob(self,number):
        """
        return the content of a blob

        @param number: the internal number of the blob
        """
        blob=Storage(self.path,"blob%d" % number)
        return blob.content()
