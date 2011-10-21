from __future__ import with_statement
import os
import re
from storage import Storage
from common import check_output
from werkzeug.datastructures import FileStorage

class MetaBlob:
    def __init__(self, label, comment, filename):
        self.label = label
        self.comment = comment
        self.filename = filename

class Blob:
    def __init__(self, data, label, comment, filename):
        self.data = data
        self.label = label
        self.comment = comment
        self.filename = filename

class CourseLite:
    """
    Backend for viewing the file structres related to a course

    A detailed description can be found with the class Course.
    """
    def __init__(self, obj):
        """
        constructor for CourseLite objects

        @param obj: either the path to a coures or a Course object
        @type obj: str or Course or CourseLite
        """
        if isinstance(obj, CourseLite):
            self.path = obj.path
        else:
            assert isinstance(obj, str)
            if not os.path.isdir(obj):
                return None
            self.path = obj

    @property
    def name(self):
        """
        @rtype: str
        """
        return os.path.basename(self.path)

    def gettitle(self):
        """
        @returns: title of the course
        @rtype: unicode
        """
        s=Storage(self.path,"title")
        return s.content().decode("utf8")

    def nextpage(self,havelock=False):
        """
        internal function: return the number of the next available page, but don't do anything
        @rtype: int
        """
        s = Storage(self.path,"nextpage")
        vs = s.content(havelock=havelock)
        if vs=='':
            vs='0'
        return int(vs)

    def nextblob(self,havelock=False):
        """
        internal function: return the number of the next available blob, but don't do anything

        @returns: number of next available blob
        @rtype: int
        """
        s = Storage(self.path,"nextblob")
        vs = s.content(havelock=havelock)
        if vs=='':
            vs='0'
        return int(vs)

    def listpages(self,havelock=False):
        """
        @returns: a list of the available page numbers in correct order
        @rtype: [int]
        """
        indexstore = Storage(self.path,"Index")
        index = indexstore.content(havelock=havelock)
        lines = index.splitlines()
        return [int(line.split()[0]) for line in lines]

    def listdeadpages(self):
        """
        @returns: a list of the pages not currently linked in the index
        @rtype: [int]
        """
        indexstore = Storage(self.path, "Index")
        nextpage = Storage(self.path, "nextpage")
        with indexstore.lock as gotlockindex:
            with nextpage.lock as gotlocknextpage:
                np = self.nextpage(havelock=gotlocknextpage)
                linkedpages= self.listpages(havelock=gotlockindex)
                return [x for x in range(np) if x not in linkedpages]
            
    def listdeadblobs(self):
        """
        @returns: a list of the blobs not currently linked to the index
        @rtype: [int]
        """
        indexstore = Storage(self.path,"Index")
        nextblob = Storage(self.path,"nextblob")
        with indexstore.lock as gotlockindex:
            index = indexstore.content(havelock=gotlockindex)
            lines = index.splitlines()
            availableblobs = []
            for line in lines:
                entries = line.split()
                availableblobs.extend([int(x) for x in entries[1:]])
            with nextblob.lock as gotlocknextblob:
                nextblobindex = self.nextblob(havelock=gotlocknextblob)
                return [n for n in range(nextblobindex) if n not in availableblobs]


    def showpage(self,number):
        """
        Show the contents of a page

        @type number: int
        @param number: the internal number of that page
        @rtype: unicode
        """
        assert isinstance(number, int)
        page = Storage(self.path,"page%d" % number)
        return page.content().decode("utf8")


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

    blobN,v          The blob with the internal number N
    blobN.label,v    The label for the blob with internal number N
    blobN.comment,v  The comment for the blob with internal number N
    blobN.filename,v The filename for the blob with internal number N

    nextpage,v contains the number of the next available page
    nextblob,v contains the number of the next available blob
    """
    def __init__(self, obj):
        """
        constructor for Course objects

        @param obj: either the path to a coures or a Course object
        @type obj: str or Course or CourseLite
        """
        if not isinstance(obj, CourseLite):
            try:
                os.makedirs(obj)
            except os.error:
                pass
        CourseLite.__init__(self, obj)

    def export(self):
        """
        @returns: a tar ball containing the full internal information about
                this course
        @rtype: str
        """
        return check_output(["tar","cf","-",self.path])
    
    def settitle(self,title):
        """
        Set the title of this course
        @type title: unicode
        """
        assert isinstance(title, unicode)
        s=Storage(self.path,"title")
        s.store(title.encode("utf8"))

    def newpage(self,user=None):
        """
        create a new page in this course and return its internal number
        @type user: None or unicode
        @rtype: int
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        index = Storage(self.path,"Index")
        nextpagestore = Storage(self.path,"nextpage")
        with index.lock as gotlockindex:
            with nextpagestore.lock as gotlocknextpage:
                newnumber = self.nextpage(havelock=gotlocknextpage)
                nextpagestore.store("%d" % (newnumber+1),havelock=gotlocknextpage,user=user)
                indexcontents = index.content(havelock=gotlockindex)
                indexcontents += "%s\n" % newnumber
                index.store(indexcontents,havelock=gotlockindex,user=user)
                return newnumber

    def delblob(self,number,user=None):
        """
        Delete a page

        @param number: the internal page number
        @type number: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = Storage(self.path,"Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock=gotlock)
            lines = index.splitlines()
            newlines = []
            for line in lines:
                entries = line.split()
                newentries = [entries[0]]
                newentries.extend([x for x in entries[1:] if int(x) != number])
                newlines.append(" ".join(newentries))
            newindex="\n".join(newlines) + "\n"
            indexstore.store(newindex,havelock=gotlock,user=user)

    def delpage(self,number,user=None):
        """
        Delete a page

        @param number: the internal page number
        @type number: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = Storage(self.path,"Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock=gotlock)
            lines = index.splitlines()
            newlines = []
            for line in lines:
                if int(line.split()[0])!=number:
                    newlines.append(line)
            newindex="\n".join(newlines) + "\n"
            indexstore.store(newindex,havelock=gotlock,user=user)

    def swappages(self,position,user=None):
        """
        swap the page at the given current position with its predecessor

        @type position: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = Storage(self.path,"Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock=gotlock)
            lines = index.splitlines()
            if position<len and position>0:
                tmp =lines[position-1]
                lines[position-1]=lines[position]
                lines[position]=tmp
            newindex="\n".join(lines) + "\n"
            indexstore.store(newindex,havelock=gotlock,user=user)

    def relink(self, page, user=None):
        """
        relink a (usually deleted) page to the index
        @type page: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = Storage(self.path, "Index")
        nextpage = Storage(self.path, "nextpage")
        with indexstore.lock as gotlockindex:
            with nextpage.lock as gotlocknextpage:
                np = self.nextpage(havelock=gotlocknextpage)
                if page >= np:
                    pass # can only relink in the allowed range
                if page < 0:
                    pass # can only relink in the allowed range
                else:
                    index = indexstore.content(havelock=gotlockindex)
                    lines = index.splitlines()
                    if page in [int(x.split()[0]) for x in lines]:
                        pass # page already present
                    else:
                        lines.append("%d" % page)
                        newindex="\n".join(lines) + "\n"
                        indexstore.store(newindex,havelock=gotlockindex,user=user)

    def relinkblob(self, number, page, user=None):
        """
        relink a (usually deleted) blob to the given page in the index
        @type number: int
        @type page: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = Storage(self.path, "Index")
        nextblob = Storage(self.path, "nextblob")
        with indexstore.lock as gotlockindex:
            with nextblob.lock as gotlocknextblob:
                nb = self.nextblob(havelock=gotlocknextblob)
                if number >= nb:
                    return # can only attach an
                if number < 0:
                    return # can only attach an
                index = indexstore.content(havelock=gotlockindex)
                lines = index.splitlines()
                for i in range(len(lines)):
                    if int(lines[i].split()[0]) == page:
                        lines[i] += " %d" % number
            newindex="\n".join(lines) + "\n"
            indexstore.store(newindex,havelock=gotlockindex,user=user)
                        

    def editpage(self,number):
        """
        Start editing a page; 

        @param number: the internal page number
        @type number: int
        @returns a pair of an opaque version string and the contents of this page
        @rtype: (unicode, unicode)
        """
        page = Storage(self.path,"page%d" % number)
        version, content = page.startedit()
        return (version.decode("utf8"), content.decode("utf8"))

    def savepage(self,number,version, newcontent,user=None):
        """
        Finish editing a page

        @param number: the internal page number
        @param version: the opaque version string, as obtained from edit page
        @param newcontent: the new content of the page, based on editing the said version
        @param user: the df-login name of the user to carried out the edit
        @type number: int
        @type version: unicode
        @type newcontent: unicode
        @type user: unicode

        @returns: a triple (ok,newversion,mergedcontent) where ok is a boolean indicating
                  whether no confilct has occured and (newversion,mergedcontent) a pair
                  for further editing that can be  handled as if obtained from editpage
        @rtype: (unicode, unicode, unicode)
        """
        assert isinstance(version, unicode)
        assert isinstance(newcontent, unicode)
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        page = Storage(self.path,"page%d" % number)
        ok, version, mergedcontent = page.endedit(version.encode("utf8"),
                                                  newcontent.encode("utf8"), user=user)
        return (ok, version.decode("utf8"), mergedcontent.decode("utf8"))

    def attachblob(self, number, data, comment="unknown blob", label="fig", user=None):
        """
        Attach a blob to a page

        @param number: the internal number of the page
        @param comment: a human readable description, e.g., the caption to be added to this figure
        @param label: a short label for the blob (only small letters and digits allowed)
        @param user: the df-login name of the user to carried out the edit
        @type number: int
        @type data: str or file-like
        @type label: unicode
        @Type comment: unicode
        @type user: unicode or None
        """
        assert isinstance(data, FileStorage)
        assert isinstance(comment, unicode)
        assert isinstance(label, unicode)

        if re.match('^[a-z0-9]{1,200}$', label) is None:
            return False

        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = Storage(self.path,"Index")
        nextblobstore = Storage(self.path,"nextblob")

        with indexstore.lock as gotlockindex:
            with nextblobstore.lock as gotlocknextblob:
                newnumber = self.nextblob(havelock=gotlocknextblob)
                nextblobstore.store("%d" % (newnumber+1),havelock=gotlocknextblob)
                index = indexstore.content()
                lines = index.splitlines()
                for i in range(len(lines)):
                    if int(lines[i].split()[0])==number:
                        lines[i] += " %d" % newnumber
                        newindex="\n".join(lines) + "\n"
                        indexstore.store(newindex,havelock=gotlockindex)

        blob = Storage(self.path,"blob%d" % newnumber)
        bloblabel = Storage(self.path,"blob%d.label" % newnumber)
        blobcomment = Storage(self.path,"blob%d.comment" % newnumber)
        blobname = Storage(self.path,"blob%d.filename" % newnumber)
        blob.store(data, user=user)
        bloblabel.store(label.encode("utf8"), user=user)
        blobcomment.store(comment.encode("utf8"), user=user)
        blobname.store(data.filename.encode("utf8"), user=user)
        return True

    def listblobs(self,number):
        """
        return a list of the blobs associated with the given page

        @param number: the internal page number
        @type number: int
        @rtype: [int]
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

    def getblob(self, number):
        """
        return the corresponding blob

        @param number: the internal number of the blob
        @type number: int
        @rtype: Blob
        """
        return Blob(Storage(self.path,"blob%d" % number).content(),
                    Storage(self.path,"blob%d.label" % number).content().decode("utf8"),
                    Storage(self.path,"blob%d.comment" % number).content().decode("utf8"),
                    Storage(self.path,"blob%d.filename" % number).content().decode("utf8"))

    def getmetablob(self, number):
        """
        return the corresponding blob

        @param number: the internal number of the blob
        @type number: int
        @rtype: Blob
        """
        return MetaBlob(Storage(self.path,"blob%d.label" % number).content().decode("utf8"),
                        Storage(self.path,"blob%d.comment" % number).content().decode("utf8"),
                        Storage(self.path,"blob%d.filename" % number).content().decode("utf8"))
