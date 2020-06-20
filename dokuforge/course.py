import os
import datetime
import typing

from werkzeug.datastructures import FileStorage

from dokuforge.storage import LockDir
from dokuforge.storagedir import StorageDir
from dokuforge.view import LazyView, liftdecodeutf8
from dokuforge.parser import dfLineGroupParser, dfTitleParser, dfCaptionParser
from dokuforge.parser import Estimate, PHeading
import dokuforge.common as common

class Outline:
    def __init__(self, number: int) -> None:
        self.number = number
        self.content = []
        self.lastchange = {'author': 'unkown', 'revision': '?',
                           'date': common.epoch}
        self.estimate = Estimate.fromNothing()

    def addheading(self, title: str) -> None:
        assert isinstance(title, str)
        if title:
            self.content.append(("heading", title))

    def addsubheading(self, title: str) -> None:
        assert isinstance(title, str)
        if title:
            self.content.append(("subheading", title))

    def addParsed(self, headinglist: typing.List[PHeading]) -> None:
        for heading in headinglist:
            if heading.getLevel() == 0:
                self.addheading(heading.getTitle())
            else:
                self.addsubheading(heading.getTitle())

    def items(self) -> typing.List[typing.Tuple[str, str]]:
        return self.content

    def addEstimate(self, estimate: Estimate) -> None:
        assert isinstance(estimate, Estimate)
        self.estimate = estimate

    def addcommitinfo(self,
                      info: typing.Dict[str,
                                        typing.Union[str,
                                                     datetime.datetime]]) -> \
            None:
        """
        Add information about the last commit. Must contain at
        least revision, date, and author
        """
        assert 'date' in info.keys()
        assert 'author'  in info.keys()
        assert 'revision' in info.keys()

        self.lastchange = info
    @property
    def versionstring(self) -> str:
        return "%s/%s (%s)" % (self.lastchange['revision'],
                                self.lastchange['author'],
                                self.lastchange['date'].strftime("%Y/%m/%d %H:%M:%S %Z"))

class Course(StorageDir):
    """
    Backend for manipulating the file structres related to a course

    A course is described by a directory. This directory may contain, among
    other things, the following files; with each rcs file, the associated file
    and locks as described in L{Storage} can be present as well.

     - title,v --
         The title of this course (as to be printed)
     - isDeleted,v --
         A bit indicating whether the course is to be hidden from the list
         of courses; defaults to false.
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
    def __init__(self, obj: typing.Union[bytes, "Course"]) -> None:
        """
        constructor for Course objects

        @param obj: either the path to a coures or a Course object
        """
        StorageDir.__init__(self, obj)
        try:
            os.makedirs(self.path)
        except os.error:
            pass

    @property
    def isDeleted(self):
        value = self.getcontent(b"isDeleted")
        return value == b"True"

    def delete(self) -> None:
        self.getstorage(b"isDeleted").store(b"True")

    def undelete(self) -> None:
        self.getstorage(b"isDeleted").store(b"False")

    def nextpage(self, havelock: typing.Optional[LockDir] = None) -> int:
        """
        internal function: return the number of the next available page, but don't do anything
        """
        return int(self.getcontent(b"nextpage", havelock) or "0")

    def nextblob(self, havelock: typing.Optional[LockDir] = None) -> int:
        """
        internal function: return the number of the next available blob, but don't do anything

        @returns: number of next available blob
        """
        return int(self.getcontent(b"nextblob", havelock) or "0")

    def listpages(self, havelock: typing.Optional[LockDir] = None) -> \
            typing.List[int]:
        """
        @returns: a list of the available page numbers in correct order
        """
        lines = self.getcontent(b"Index", havelock).splitlines()
        return [int(line.split()[0]) for line in lines if line != b""]

    def outlinepages(self, havelock: typing.Optional[LockDir] = None) -> \
            typing.List[Outline]:
        """
        @returns: a list of the available pages with information such as
            headings cointained in correct order
        """
        pages = self.listpages()
        outlines = []
        for p in pages:
            outline = Outline(p)
            outline.addcommitinfo(self.getcommit(p))
            parsed = dfLineGroupParser(self.showpage(p))
            headings =  [x for x in parsed.parts if isinstance(x, PHeading)]
            outline.addParsed(headings)
            theestimate = parsed.toEstimate()
            theestimate += Estimate.fromBlobs(self.listblobs(p))
            outline.addEstimate(theestimate)
            outlines.append(outline)
        return outlines

    def getcommit(self, page: int) -> \
            typing.Dict[str, typing.Union[str, datetime.datetime]]:
        info = self.getstorage(b"page%d" % page).commitstatus()
        return dict((k.decode("ascii"), v) if k == b"date"
                    else (k.decode("ascii"), v.decode("utf8"))
                    for k, v in info.items())

    def listdeadpages(self) -> typing.List[int]:
        """
        @returns: a list of the pages not currently linked in the index
        """
        indexstore = self.getstorage(b"Index")
        nextpage = self.getstorage(b"nextpage")
        with indexstore.lock as gotlockindex:
            with nextpage.lock as gotlocknextpage:
                np = self.nextpage(havelock = gotlocknextpage)
                linkedpages = self.listpages(havelock = gotlockindex)
                return [x for x in range(np) if x not in linkedpages]

    def outlinedeadpages(self) -> typing.List[Outline]:
        """
        @returns: a list of the outlines of the pages not currently linked
            in the index (shortened to headings).
        """
        outlines = []
        for p in self.listdeadpages():
            outline = Outline(p)
            parsed = dfLineGroupParser(self.showpage(p))
            headings =  [x for x in parsed.parts if isinstance(x, PHeading)]
            outline.addParsed(headings)
            outlines.append(outline)
        return outlines

    def listdeadblobs(self) -> typing.List[int]:
        """
        @returns: a list of the blobs not currently linked to the index
        """
        indexstore = self.getstorage(b"Index")
        nextblob = self.getstorage(b"nextblob")
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

    def showpage(self, number: int) -> str:
        """
        Show the contents of a page

        @param number: the internal number of that page
        """
        return self.getcontent(b"page%d" % number).decode("utf8")

    def getrcs(self, page) -> str:
        """
        @param page: the internal number of the page
        @returns: an rcs file describing all versions of this page
        """
        if 0 > page:
            return ""
        if page >= self.nextpage():
            return ""
        return self.getstorage(b"page%d" % page).asrcs()

    def newpage(self, user: typing.Optional[str] = None) -> int:
        """
        create a new page in this course and return its internal number
        """
        userb = None
        if user is not None:
            assert isinstance(user, str)
            userb = user.encode("utf8")
        index = self.getstorage(b"Index")
        nextpagestore = self.getstorage(b"nextpage")
        with index.lock as gotlockindex:
            with nextpagestore.lock as gotlocknextpage:
                newnumber = self.nextpage(havelock = gotlocknextpage)
                nextpagestore.store(b"%d" % (newnumber + 1),
                                    havelock=gotlocknextpage, user=userb)
                indexcontents = index.content(havelock = gotlockindex)
                if indexcontents == b"\n":
                    indexcontents = b""
                indexcontents += b"%d\n" % newnumber
                index.store(indexcontents, havelock=gotlockindex, user=userb)
                return newnumber

    def delblob(self, number: int, user: typing.Optional[str] = None) -> None:
        """
        Delete a page

        @param number: the internal page number
        """
        userb = None
        if user is not None:
            assert isinstance(user, str)
            userb = user.encode("utf8")
        indexstore = self.getstorage(b"Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock = gotlock)
            lines = index.splitlines()
            newlines = []
            for line in lines:
                entries = line.split()
                if not entries:
                    continue
                newentries = [entries[0]]
                newentries.extend([x for x in entries[1:] if int(x) != number])
                newlines.append(b" ".join(newentries))
            newindex = b"".join(map(b"%s\n".__mod__, newlines))
            indexstore.store(newindex, havelock=gotlock, user=userb)

    def delpage(self, number: int, user: typing.Optional[str] = None) -> None:
        """
        Delete a page

        @param number: the internal page number
        """
        userb = None
        if user is not None:
            assert isinstance(user, str)
            userb = user.encode("utf8")
        indexstore = self.getstorage(b"Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock = gotlock)
            lines = index.splitlines()
            newlines = []
            for line in lines:
                entries = line.split()
                if entries and int(entries[0]) != number:
                    newlines.append(line)
            newindex = b"".join(map(b"%s\n".__mod__, newlines))
            indexstore.store(newindex, havelock=gotlock, user=userb)

    def swappages(self, position: int, user: typing.Optional[str] = None) -> \
            None:
        """
        swap the page at the given current position with its predecessor
        """
        userb = None
        if user is not None:
            assert isinstance(user, str)
            userb = user.encode("utf8")
        indexstore = self.getstorage(b"Index")
        with indexstore.lock as gotlock:
            index = indexstore.content(havelock = gotlock)
            lines = index.splitlines()
            if position < len(lines) and position > 0:
                tmp = lines[position-1]
                lines[position-1] = lines[position]
                lines[position] = tmp
            newindex = b"".join(map(b"%s\n".__mod__, lines))
            indexstore.store(newindex, havelock=gotlock, user=userb)

    def relink(self, page: int, user: typing.Optional[str] = None) -> None:
        """
        relink a (usually deleted) page to the index
        """
        userb = None
        if user is not None:
            assert isinstance(user, str)
            userb = user.encode("utf8")
        indexstore = self.getstorage(b"Index")
        nextpage = self.getstorage(b"nextpage")
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
                    lines = [x for x in lines if x != b""]
                    if page in [int(x.split()[0]) for x in lines]:
                        pass # page already present
                    else:
                        lines.append(b"%d" % page)
                        newindex = b"".join(map(b"%s\n".__mod__, lines))
                        indexstore.store(newindex, havelock = gotlockindex,
                                         user=userb)

    def relinkblob(self, number: int, page: int,
                   user: typing.Optional[str] = None) -> None:
        """
        relink a (usually deleted) blob to the given page in the index
        """
        userb = None
        if user is not None:
            assert isinstance(user, str)
            userb = user.encode("utf8")
        indexstore = self.getstorage(b"Index")
        nextblob = self.getstorage(b"nextblob")
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
                    if lineparts and int(lineparts[0]) == page:
                        if number in [int(x) for x in lineparts[1:]]:
                            pass # want a set-like semantics
                        else:
                            lines[i] += b" %d" % number
            newindex = b"".join(map(b"%s\n".__mod__, lines))
            indexstore.store(newindex, havelock=gotlockindex, user=userb)

    def editpage(self, number: int) -> typing.Tuple[str, str]:
        """
        Start editing a page;

        @param number: the internal page number
        @returns: a pair of an opaque version string and the contents of this page
        """
        page = self.getstorage(b"page%d" % number)
        version, content = page.startedit()
        return (version.decode("utf8"), content.decode("utf8"))

    def savepage(self, number: int, version: str, newcontent: str,
                 user: str = None) -> typing.Tuple[str, str, str]:
        """
        Finish editing a page

        @param number: the internal page number
        @param version: the opaque version string, as obtained from edit page
        @param newcontent: the new content of the page, based on editing the said version
        @param user: the df-login name of the user to carried out the edit
        @returns: a triple (ok, newversion, mergedcontent) where ok is a
                  boolean indicating whether no confilct has occured and
                  (newversion, mergedcontent) a pair for further editing that
                  can be handled as if obtained from editpage
        """
        assert isinstance(version, str)
        assert isinstance(newcontent, str)
        userb = None
        if user is not None:
            assert isinstance(user, str)
            userb = user.encode("utf8")
        page = self.getstorage(b"page%d" % number)
        ok, newversion, mergedcontent = page.endedit(version.encode("utf8"),
                                                     newcontent.encode("utf8"),
                                                     user=userb)
        return (ok, newversion.decode("utf8"), mergedcontent.decode("utf8"))

    def attachblob(self, number: int, data: FileStorage,
                   comment: str = "unknown blob", label: str = "fig",
                   user: typing.Optional[str] = None):
        """
        Attach a blob to a page

        @param number: the internal number of the page
        @param comment: a human readable description, e.g., the caption to be
            added to this figure
        @param label: a short label for the blob (only small letters and
            digits allowed)
        @param user: the df-login name of the user to carried out the edit
        @type data: str or file-like
        @returns: None on failure or the created blob number
        """
        assert isinstance(data, FileStorage)
        assert isinstance(comment, str)
        assert isinstance(label, str)

        common.validateBlobLabel(label)
        common.validateBlobComment(comment)
        # Note: Some browsers may be unable to set the filename.
        filename = (data.filename or "").encode("utf8")
        common.validateBlobFilename(filename)

        userb = None
        if user is not None:
            assert isinstance(user, str)
            userb = user.encode("utf8")
        indexstore = self.getstorage(b"Index")
        nextblobstore = self.getstorage(b"nextblob")

        with indexstore.lock as gotlockindex:
            with nextblobstore.lock as gotlocknextblob:
                newnumber = self.nextblob(havelock = gotlocknextblob)
                nextblobstore.store(b"%d" % (newnumber + 1),
                                    havelock = gotlocknextblob)
                index = indexstore.content()
                lines = index.splitlines()
                for i in range(len(lines)):
                    entries = lines[i].split()
                    if entries and int(entries[0]) == number:
                        lines[i] += b" %d" % newnumber
                        newindex = b"".join(map(b"%s\n".__mod__, lines))
                        indexstore.store(newindex, havelock = gotlockindex)

        blobbase = b"blob%d" % newnumber
        blob = self.getstorage(blobbase)
        bloblabel = self.getstorage(blobbase + b".label")
        blobcomment = self.getstorage(blobbase + b".comment")
        blobname = self.getstorage(blobbase + b".filename")
        blob.store(data, user=userb)
        bloblabel.store(label.encode("utf8"), user=userb)
        blobcomment.store(comment.encode("utf8"), user=userb)
        blobname.store(filename, user=userb)
        return newnumber

    def listblobs(self, number: int) -> typing.List[int]:
        """
        return a list of the blobs associated with the given page

        @param number: the internal page number
        """
        for line in self.getcontent(b"Index").splitlines():
            entries = line.split()
            if entries and int(entries[0]) == number:
                entries.pop(0)
                return [int(x) for x in entries]
        return []

    def viewblob(self, number: int) -> LazyView:
        """
        return the corresponding blob

        @param number: the internal number of the blob
        @returns: a mapping providing the keys: data(str), label(str),
                  comment(str), filename(str) and number(int)
        """
        ldu = liftdecodeutf8
        blobbase = b"blob%d" % number
        return LazyView(dict(
            data = self.getstorage(blobbase).content,
            label = ldu(self.getstorage(blobbase + b".label").content),
            comment = ldu(self.getstorage(blobbase + b".comment").content),
            filename = ldu(self.getstorage(blobbase + b".filename").content),
            number = lambda:number))

    def modifyblob(self, number, label: str, comment: str, filename: str,
                   user: str) -> None:
        """
        modify the blob given by number with the data in the other parameters.
        @raises CheckError: if the input data is malformed
        """
        assert isinstance(label, str)
        assert isinstance(comment, str)
        assert isinstance(filename, str)
        assert isinstance(user, str)

        # store requires user to be bytes, so encode
        userb = user.encode("utf-8")

        filenameb = filename.encode("utf8")
        common.validateBlobLabel(label)
        common.validateBlobComment(comment)
        common.validateBlobFilename(filenameb)

        blobbase = b"blob%d" % number
        bloblabel = self.getstorage(blobbase + b".label")
        blobcomment = self.getstorage(blobbase + b".comment")
        blobname = self.getstorage(blobbase + b".filename")
        bloblabel.store(label.encode("utf8"), user=userb)
        blobcomment.store(comment.encode("utf8"), user=userb)
        blobname.store(filenameb, user=userb)

    def lastchange(self):
        return common.findlastchange([self.getcommit(p) for p in self.listpages()])

    def timestamp(self):
        return max([self.getstorage(b"page%d" % p).timestamp()
                    for p in self.listpages()] + [common.epoch])

    def view(self, extrafunctions=dict()) -> LazyView:
        """
        @returns: a mapping providing the keys: name(bytes), pages([int]),
                deadpages([int]), title(str), outlines([Outline])
        """
        functions = dict(
            pages = self.listpages,
            deadpages = self.listdeadpages,
            outlines = self.outlinepages,
            outlinesdead = self.outlinedeadpages,
            lastchange = self.lastchange,
            timestamp = self.timestamp)
        functions.update(extrafunctions)
        return StorageDir.view(self, functions)

    def texExportIterator(self, tarwriter):
        """
        yield the contents of the course as tex-export.
        """
        tex = "\\course{%02d}{%s}" % (self.number,
                                       dfTitleParser(self.gettitle()).toTex().strip())
        for p in self.listpages():
            tex += "\n\n%%%%%% Part %d\n" % p
            page = self.showpage(p)
            tex += dfLineGroupParser(page).toTex()
            for b in self.listblobs(p):
                blob = self.viewblob(b)
                blobbase = b"blob%d" % b
                blobdate = self.getstorage(blobbase).commitstatus()[b'date']
                tex += "\n\n%% blob %d\n" % b
                tex += "\\begin{figure}\n\\centering\n"
                fileName = blob['filename']
                includegraphics = \
                    ("\\includegraphics" +
                     "[height=12\\baselineskip]{%s/blob_%d_%s}\n") % \
                    (self.name.decode('ascii'), b, fileName)
                if fileName.lower().endswith((".png", ".jpg", ".pdf")):
                    tex += includegraphics
                else:
                    tex += ("%%%s(Binaerdatei \\verb|%s|" +
                            " nicht als Bild eingebunden)\n") % \
                           (includegraphics, fileName)
                tex += "\\caption{%s}\n" % dfCaptionParser(
                    blob['comment']).toTex().strip()
                tex += "\\label{fig_%s_%d_%s}\n" % (
                    self.name.decode('ascii'), b, blob['label'])
                tex += "\\end{figure}\n"
                yield tarwriter.addChunk(b"%s/blob_%d_%s" %
                                         (self.name, b,
                                          blob['filename'].encode("utf8")),
                                         blob['data'],
                                         blobdate)

        yield tarwriter.addChunk(self.name + b"/chap.tex",
                                 tex.encode("utf8"),
                                 self.lastchange()['date'])
