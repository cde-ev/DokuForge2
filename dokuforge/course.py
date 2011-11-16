from __future__ import with_statement
import os
import re

from werkzeug.datastructures import FileStorage

from dokuforge.common import check_output
from dokuforge.storagedir import StorageDir
from dokuforge.view import LazyView, liftdecodeutf8
import dokuforge.common as common

class Outline:
    def __init__(self, number):
        """
        @type number: int
        """
        self.number = number
        self.content = []
    def addheading(self, title):
        """
        @type title: unicode
        """
        assert isinstance(title, unicode)
        if title:
            self.content.append(("heading", title))
    def addsubheading(self, title):
        """
        @type title: unicode
        """
        assert isinstance(title, unicode)
        if title:
            self.content.append(("subheading", title))
    def items(self):
        """
        @rtype: [(str, unicode)]
        """
        return self.content

class Course(StorageDir):
    """
    Backend for manipulating the file structres related to a course

    A course is described by a directory. This directory may contain, among
    other things, the following files; with each rcs file, the associated file
    and locks as described in L{Storage} can be present as well.

     - title,v --
         The title of this course (as to be printed)
     - Index,v --
         List of internal page numbers, in order of appearence
         Each line contains the internal page number, followed by a space,
         optionally followed by internal blob-numbers associated with page.
     - pageN,v --
         The page with internal number N
     - blobN,v --
         The blob with the internal number N
     - blobN.label,v --
         The label for the blob with internal number N
     - blobN.comment,v --
         The comment for the blob with internal number N
     - blobN.filename,v --
         The filename for the blob with internal number N
     - nextpage,v --
         contains the number of the next available page
     - nextblob,v --
         contains the number of the next available blob
    """
    def __init__(self, obj):
        """
        constructor for Course objects

        @param obj: either the path to a coures or a Course object
        @type obj: str or Course
        """
        StorageDir.__init__(self, obj)
        try:
            os.makedirs(self.path)
        except os.error:
            pass

    def nextpage(self, havelock=None):
        """
        internal function: return the number of the next available page, but don't do anything
        @type havelock: None or LockDir
        @rtype: int
        """
        return int(self.getcontent("nextpage", havelock) or "0")

    def nextblob(self, havelock=None):
        """
        internal function: return the number of the next available blob, but don't do anything

        @type havelock: None or LockDir
        @returns: number of next available blob
        @rtype: int
        """
        return int(self.getcontent("nextblob", havelock) or "0")

    def listpages(self, havelock=None):
        """
        @type havelock: None or LockDir
        @returns: a list of the available page numbers in correct order
        @rtype: [int]
        """
        lines = self.getcontent("Index", havelock).splitlines()
        return [int(line.split()[0]) for line in lines if line != ""]

    def outlinepages(self, havelock=None):
        """
        @type havelock: None or LockDir
        @returns: a list of the available pages with information such as
            headings cointained in correct order
        @rtype: [Outline]
        """
        pages = self.listpages()
        outlines = []
        for p in pages:
            outline = Outline(p)
            headings = re.findall(ur'^\[.*\]$', self.showpage(p),
                                  re.MULTILINE|re.UNICODE)
            for h in headings:
                if h[1] == u'[':
                    outline.addsubheading(h[2:-2])
                else:
                    outline.addheading(h[1:-1])
            outlines.append(outline)
        return outlines

    def listdeadpages(self):
        """
        @returns: a list of the pages not currently linked in the index
        @rtype: [int]
        """
        indexstore = self.getstorage("Index")
        nextpage = self.getstorage("nextpage")
        with indexstore.lock as gotlockindex:
            with nextpage.lock as gotlocknextpage:
                np = self.nextpage(havelock = gotlocknextpage)
                linkedpages = self.listpages(havelock = gotlockindex)
                return [x for x in range(np) if x not in linkedpages]

    def listdeadblobs(self):
        """
        @returns: a list of the blobs not currently linked to the index
        @rtype: [int]
        """
        indexstore = self.getstorage("Index")
        nextblob = self.getstorage("nextblob")
        with indexstore.lock as gotlockindex:
            index = indexstore.content(havelock = gotlockindex)
            lines = index.splitlines()
            availableblobs = []
            for line in lines:
                entries = line.split()
                availableblobs.extend([int(x) for x in entries[1:]])
            with nextblob.lock as gotlocknextblob:
                nextblobindex = self.nextblob(havelock = gotlocknextblob)
                return [n for n in range(nextblobindex) if n not in availableblobs]


    def showpage(self, number):
        """
        Show the contents of a page

        @type number: int
        @param number: the internal number of that page
        @rtype: unicode
        """
        return self.getcontent("page%d" % number).decode("utf8")

    def getrcs(self, page):
        """
        @param page: the internal number of the page
        @returns: an rcs file describing all versions of this page
        @rtype: str
        """
        if 0 > page:
            return ""
        if page >= self.nextpage():
            return ""
        return self.getstorage("page%d" % page).asrcs()

    def export(self):
        """
        @returns: a tar ball containing the full internal information about
                this course
        @rtype: str
        """
        return check_output(["tar", "cf", "-", self.path])

    def newpage(self, user=None):
        """
        create a new page in this course and return its internal number
        @type user: None or unicode
        @rtype: int
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        index = self.getstorage("Index")
        nextpagestore = self.getstorage("nextpage")
        with index.lock as gotlockindex:
            with nextpagestore.lock as gotlocknextpage:
                newnumber = self.nextpage(havelock = gotlocknextpage)
                nextpagestore.store("%d" % (newnumber+1),
                                    havelock = gotlocknextpage, user = user)
                indexcontents = index.content(havelock = gotlockindex)
                if indexcontents == "\n":
                    indexcontents = ""
                indexcontents += "%s\n" % newnumber
                index.store(indexcontents, havelock = gotlockindex, user = user)
                return newnumber

    def delblob(self, number, user=None):
        """
        Delete a page

        @param number: the internal page number
        @type number: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = self.getstorage("Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock = gotlock)
            lines = index.splitlines()
            newlines = []
            for line in lines:
                entries = line.split()
                newentries = [entries[0]]
                newentries.extend([x for x in entries[1:] if int(x) != number])
                newlines.append(" ".join(newentries))
            newindex = "\n".join(newlines) + "\n"
            indexstore.store(newindex, havelock = gotlock, user = user)

    def delpage(self, number, user=None):
        """
        Delete a page

        @param number: the internal page number
        @type number: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = self.getstorage("Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock = gotlock)
            lines = index.splitlines()
            newlines = []
            for line in lines:
                if int(line.split()[0]) != number:
                    newlines.append(line)
            newindex = "\n".join(newlines) + "\n"
            indexstore.store(newindex, havelock = gotlock, user = user)

    def swappages(self, position, user=None):
        """
        swap the page at the given current position with its predecessor

        @type position: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = self.getstorage("Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock = gotlock)
            lines = index.splitlines()
            if position < len and position > 0:
                tmp = lines[position-1]
                lines[position-1] = lines[position]
                lines[position] = tmp
            newindex = "\n".join(lines) + "\n"
            indexstore.store(newindex, havelock = gotlock, user = user)

    def relink(self, page, user=None):
        """
        relink a (usually deleted) page to the index
        @type page: int
        @type user: None or unicode
        """
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = self.getstorage("Index")
        nextpage = self.getstorage("nextpage")
        with indexstore.lock as gotlockindex:
            with nextpage.lock as gotlocknextpage:
                np = self.nextpage(havelock = gotlocknextpage)
                if page >= np:
                    pass # can only relink in the allowed range
                if page < 0:
                    pass # can only relink in the allowed range
                else:
                    index = indexstore.content(havelock = gotlockindex)
                    lines = index.splitlines()
                    lines = [ x for x in lines if x != ""]
                    if page in [int(x.split()[0]) for x in lines]:
                        pass # page already present
                    else:
                        lines.append("%d" % page)
                        newindex = "\n".join(lines) + "\n"
                        indexstore.store(newindex, havelock = gotlockindex,
                                         user = user)

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
        indexstore = self.getstorage("Index")
        nextblob = self.getstorage("nextblob")
        with indexstore.lock as gotlockindex:
            with nextblob.lock as gotlocknextblob:
                nb = self.nextblob(havelock = gotlocknextblob)
                if number >= nb:
                    return # can only attach an
                if number < 0:
                    return # can only attach an
                index = indexstore.content(havelock = gotlockindex)
                lines = index.splitlines()
                for i in range(len(lines)):
                    lineparts = lines[i].split()
                    if int(lineparts[0]) == page:
                        if number in [int(x) for x in lineparts[1:]]:
                            pass # want a set-like semantics
                        else:
                            lines[i] += " %d" % number
            newindex = "\n".join(lines) + "\n"
            indexstore.store(newindex, havelock = gotlockindex, user = user)


    def editpage(self, number):
        """
        Start editing a page;

        @param number: the internal page number
        @type number: int
        @returns: a pair of an opaque version string and the contents of this page
        @rtype: (unicode, unicode)
        """
        page = self.getstorage("page%d" % number)
        version, content = page.startedit()
        return (version.decode("utf8"), content.decode("utf8"))

    def savepage(self, number, version, newcontent, user=None):
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

        @returns: a triple (ok, newversion, mergedcontent) where ok is a
                  boolean indicating whether no confilct has occured and
                  (newversion, mergedcontent) a pair for further editing that
                  can be handled as if obtained from editpage
        @rtype: (unicode, unicode, unicode)
        """
        assert isinstance(version, unicode)
        assert isinstance(newcontent, unicode)
        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        page = self.getstorage("page%d" % number)
        ok, version, mergedcontent = page.endedit(version.encode("utf8"),
                                                  newcontent.encode("utf8"),
                                                  user = user)
        return (ok, version.decode("utf8"), mergedcontent.decode("utf8"))

    def attachblob(self, number, data, comment="unknown blob", label="fig",
                   user=None):
        """
        Attach a blob to a page

        @param number: the internal number of the page
        @param comment: a human readable description, e.g., the caption to be
            added to this figure
        @param label: a short label for the blob (only small letters and
            digits allowed)
        @param user: the df-login name of the user to carried out the edit
        @type number: int
        @type data: str or file-like
        @type label: unicode
        @type comment: unicode
        @type user: unicode or None
        @returns: None on failure or the created blob number
        """
        assert isinstance(data, FileStorage)
        assert isinstance(comment, unicode)
        assert isinstance(label, unicode)

        common.validateBlobLabel(label)
        common.validateBlobComment(comment)
        # Note: Some browsers may be unable to set the filename.
        filename = (data.filename or u"unnamedfile").encode("utf8")
        common.validateBlobFilename(filename)

        if user is not None:
            assert isinstance(user, unicode)
            user = user.encode("utf8")
        indexstore = self.getstorage("Index")
        nextblobstore = self.getstorage("nextblob")

        with indexstore.lock as gotlockindex:
            with nextblobstore.lock as gotlocknextblob:
                newnumber = self.nextblob(havelock = gotlocknextblob)
                nextblobstore.store("%d" % (newnumber+1),
                                    havelock = gotlocknextblob)
                index = indexstore.content()
                lines = index.splitlines()
                for i in range(len(lines)):
                    if int(lines[i].split()[0]) == number:
                        lines[i] += " %d" % newnumber
                        newindex = "\n".join(lines) + "\n"
                        indexstore.store(newindex, havelock = gotlockindex)

        blob = self.getstorage("blob%d" % newnumber)
        bloblabel = self.getstorage("blob%d.label" % newnumber)
        blobcomment = self.getstorage("blob%d.comment" % newnumber)
        blobname = self.getstorage("blob%d.filename" % newnumber)
        blob.store(data, user = user)
        bloblabel.store(label.encode("utf8"), user = user)
        blobcomment.store(comment.encode("utf8"), user = user)
        blobname.store(filename, user=user)
        return newnumber

    def listblobs(self, number):
        """
        return a list of the blobs associated with the given page

        @param number: the internal page number
        @type number: int
        @rtype: [int]
        """
        for line in self.getcontent("Index").splitlines():
            entries = line.split()
            if int(entries[0]) == number:
                entries.pop(0)
                return [int(x) for x in entries]
        return []

    def viewblob(self, number):
        """
        return the corresponding blob

        @param number: the internal number of the blob
        @type number: int
        @rtype: LazyView
        @returns: a mapping providing the keys: data(str), label(unicode),
                  comment(unicode), filename(unicode) and number(int)
        """
        ldu = liftdecodeutf8
        return LazyView(dict(
            data = self.getstorage("blob%d" % number).content,
            label = ldu(self.getstorage("blob%d.label" % number).content),
            comment = ldu(self.getstorage("blob%d.comment" % number).content),
            filename = ldu(self.getstorage("blob%d.filename" % number).content),
            number = lambda:number))

    def modifyblob(self, number, label, comment, filename, user):
        """
        modify the blob given by number with the data in the other parameters.
        @raises CheckError: if the input data is malformed
        """
        assert isinstance(label, unicode)
        assert isinstance(comment, unicode)
        assert isinstance(filename, unicode)

        filename = filename.encode("utf8")
        common.validateBlobLabel(label)
        common.validateBlobComment(comment)
        common.validateBlobFilename(filename)

        bloblabel = self.getstorage("blob%d.label" % number)
        blobcomment = self.getstorage("blob%d.comment" % number)
        blobname = self.getstorage("blob%d.filename" % number)
        bloblabel.store(label.encode("utf8"), user = user)
        blobcomment.store(comment.encode("utf8"), user = user)
        blobname.store(filename.encode("utf8"), user = user)

    def view(self, extrafunctions=dict()):
        """
        @rtype: LazyView
        @returns: a mapping providing the keys: name(str), pages([int]),
                deadpages([int]), title(unicode), outlines([Outline])
        """
        functions = dict(
            pages = self.listpages,
            deadpages = self.listdeadpages,
            outlines = self.outlinepages)
        functions.update(extrafunctions)
        return StorageDir.view(self, functions)
