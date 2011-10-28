from __future__ import with_statement
from cStringIO import StringIO
import os, errno
import shutil
import time
import subprocess
import re

from dokuforge.common import check_output

def rlogv(filename):
    """
    Return the head revision of an rcs file

    (needed, as rlog -v is a FreeBSD extension)
    @type filename: str
    """
    assert isinstance(filename, str)
    f = file(filename, mode = "r")
    content = f.read()
    f.close()
    m = re.match(r'^\s*head\s*([0-9.]+)\s*;', content)
    if m:
        return m.groups()[0]
    else:
        return None

class LockDir:
    def __init__(self, path):
        """
        @type path: str"
        """
        assert isinstance(path, str)
        self.path = path
        self.lockcount = 0

    def __enter__(self):
        """
        Obtain a lock for this object. This is usually done internaly
        by more productive funcitons. Manual intervention is only necessary,
        if several locks have to be obtained before an operation can be carried
        out. Note that locks have to be obtained in lexicographic order by native
        byte order (in particular captital letter before lower case letters).

        Acquiring a this object multiple times will succeed, but you have to
        release it multiple times, too.
        """
        if self.lockcount != 0:
            self.lockcount += 1
            return self
        while True:
            try:
                os.mkdir(self.path)
                self.lockcount = 1
                return self
            except OSError, e:
                if e.errno == errno.EEXIST:
                    time.sleep(0.2) # evertthing OK, someone else has the lock
                else:
                    raise # something else went wrong

    def __exit__(self, _1, _2, _3):
        self.lockcount -= 1
        if self.lockcount == 0:
            os.rmdir(self.path)


class Storage(object):
    def __init__(self, path, filename):
        """
        A simple storage unit is described by a directory and the basename
        of a file in this direcotry. With the filename is also associated
        #lock.filename and filename,v as well as any rcs internal locks
        associated with it.
        @type path: str
        @type filename: str
        """
        assert isinstance(path, str)
        assert isinstance(filename, str)
        self.path = path
        self.filename = filename

    def fullpath(self, formatstr="%s"):
        """Join self.path with formatstr % self.filename.
        @type formatstr: str
        @param formatstr: format string that takes exactly one %s
        @rtype: str
        """
        assert isinstance(formatstr, str)
        return os.path.join(self.path, formatstr % self.filename)

    @property
    def lock(self):
        return LockDir(self.fullpath("#lock.%s"))

    def store(self, content, user=None, message="store called", havelock=None):
        """
        Store the given contents; rcs file is create if it does not
        exist already.

        @type content: str or filelike
        @param content: the content of the file
        @type message: str
        """
        if isinstance(content, basestring):
            assert isinstance(content, str)
            content = StringIO(content)

        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock = gotlock)
            subprocess.check_call(["co", "-f", "-q", "-l", self.fullpath()])
            objfile = file(self.fullpath(), mode = "w")
            shutil.copyfileobj(content, objfile)
            objfile.close()
            args = ["ci", "-q", "-f", "-m%s" % message]
            if user is not None:
                args.append("-w%s" % user)
            args.append(self.fullpath())
            subprocess.check_call(args)

    def ensureexistence(self, havelock=None):
        if not os.path.exists(self.fullpath("%s,v")):
            with havelock or self.lock:
                subprocess.check_call(["rcs", "-q", "-i", "-t-created by store",
                                       self.fullpath()])
                file(self.fullpath(), mode = "w").close()
                subprocess.check_call(["ci", "-q", "-f",
                                       "-minitial, implicit, empty commit",
                                       self.fullpath()])

    def asrcs(self, havelock=None):
        with havelock or self.lock:
            self.ensureexistence()
            f = file(self.fullpath("%s,v"), mode = "r")
            content = f.read()
            f.close()
            return content

    def status(self, havelock=None):
        """
        @rtype: str
        """
        self.ensureexistence(havelock = havelock)
        result = rlogv(self.fullpath("%s,v"))
        if result is None:
            result = rlogv(self.fullpath("RCS/%s,v"))
        return result

    def content(self, havelock=None):
        self.ensureexistence(havelock = havelock)
        return check_output(["co", "-q", "-p", "-kb", self.fullpath()])

    def startedit(self, havelock=None):
        """
        start editing a file (optimistic synchronisation)

        At dokuforge 2 we try optimistic synchronisation, i.e., we log (noch lock)
        the version at which a user started editing and at the end just verify if
        that version is still the head revision.

        @returns: an opaque version string and the contents of the file
        @rtype: (str, str)
        """
        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock = gotlock)
            status = self.status(havelock = gotlock)
            content = self.content(havelock = gotlock)
            return status, content

    def endedit(self, version, newcontent, user=None, havelock=None):
        """
        Store new contents in a safe way.

        Check if the version provided is still up to date. If so,
        store it as new head revision. If not, store it to a branch,
        merge with new head revision and return new version content pair.

        @type version: str
        @param version: the opaque version string optained from startedit
                        when the user started editing the file
        @type newcontent: str
        @param newcontent: the new content, produced by the user starting from
                           the content at the provided version
        @type user: None or str
        @returns: a triple (ok, newversion, mergedcontent) where ok is boolen
            with value True if the save was sucessfull (if not, a merge has
            to be done manually), and (newversion, mergedcontent) is a state
            for further editing that can be used as if obtained from
            startedit

        @note: the newcontents are transformed to native line ending
            (assuming a Unix host).  Therefore endedit CANNOT be used to
            store binaries (however, rcsmerge won't suggest a sensible
            merged version for binaries anyway).
        """
        assert isinstance(version, str)
        assert isinstance(newcontent, str)
        assert user is None or isinstance(user, str)
        ## Transform text to Unix line ending
        newcontent = "\n".join(newcontent.splitlines()) + "\n"
        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock = gotlock)
            currentversion = self.status(havelock = gotlock)
            if currentversion == version:
                self.store(newcontent, user = user, havelock = gotlock)
                newversion = self.status(havelock = gotlock)
                return True, newversion, newcontent
            ## conflict
            # 1.) store in a branch
            subprocess.check_call(["co", "-f", "-q", "-l%s" % version,
                                   self.fullpath()])
            objfile = file(self.fullpath(), mode = "w")
            objfile.write(newcontent)
            objfile.close()
            args = ["ci", "-f", "-q", "-u"]
            args.append("-mstoring original edit conflicting with %s in a branch" % currentversion)
            if user is not None:
                args.append("-w%s" % user)
            args.append(self.fullpath())
            subprocess.check_call(args)
            # 2.) merge in head
            os.chmod(self.fullpath(), 0600)
            subprocess.call(["rcsmerge", "-q", "-r%s" % version,
                             self.fullpath()]) # Note: non-zero exit status is
                                               # OK!
            objfile = file(self.fullpath(), mode = "r")
            mergedcontent = objfile.read()
            objfile.close()
            os.unlink(self.fullpath())
            # 3) return new state
            return False, currentversion, mergedcontent
