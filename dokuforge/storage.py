import datetime
import io
import logging
import os, errno
import shutil
import time
import subprocess
import re
try:
    unicode
except NameError:
    unicode = str

from dokuforge.common import check_output, utc, epoch
from dokuforge.common import validateRcsRevision
from dokuforge.common import RcsUserInputError

from subprocess import CalledProcessError

logger = logging.getLogger(__name__)

RCSENV = os.environ.copy()
RCSENV["LC_ALL"] = "C"

def rlogv(filename):
    """
    Return the head revision of an rcs file

    (needed, as rlog -v is a FreeBSD extension)
    @type filename: bytes
    @rtype: bytes or None
    """
    assert isinstance(filename, bytes)
    logger.debug("rlogv: looking up revision for %r" % filename)
    with open(filename, "rb") as f:
        firstline = f.readline()
    m = re.match(u'^\\s*head\\s*([0-9.]+)\\s*;', firstline.decode("ascii"))
    if m:
        return m.groups()[0].encode("ascii")
    else:
        return None

rcsseparator = b'----------------------------'

def rloghead(filename):
    """
    Get relevant information for the head revision of the given rcs file

    @type filename: bytes
    @returns: a bytes-object dict with information about the head commit; in
              particular, it will contain the keys b'revision', b'author', and
              b'date'. All values are bytes, except for the b'date' key which
              has a datetime object associated.
    """
    assert isinstance(filename, bytes)
    logger.debug("rloghead: looking up head revision info for %r" % filename)
    
    # Amzingly enough, the "official" way to obtain revision information
    # is to parse the output of rlog. This statement is obtained from
    # Thien-Thi Nguyen <ttn@gnuvola.org> (maintainer of GNU RCS) in an private
    # email on Oct 16, 2011 that also promised that such a script will never 
    # be broken by any future releases.
    answer = {}

    revision = rlogv(filename)
    answer[b'revision'] = revision
    rlog = check_output(["rlog","-q","-r%s" % revision.decode("ascii"),
                         filename], env=RCSENV)
    lines = rlog.splitlines()
    while lines[0] != rcsseparator or lines[1].split()[0] != b'revision':
        lines.pop(0)
    lines.pop(0)
    lines.pop(0)
    stateline = lines.pop(0)
    params = stateline.split(b';')
    for param in params:
        keyvalue = param.split(b': ', 1)
        if len(keyvalue) > 1:
            answer[keyvalue[0].lstrip()]=keyvalue[1]

    date = datetime.datetime.strptime(answer[b"date"].decode("ascii"),
                                      "%Y/%m/%d %H:%M:%S")
    answer[b"date"] = date.replace(tzinfo=utc)
    return answer

class LockDir:
    def __init__(self, path):
        """
        @type path: bytes"
        """
        assert isinstance(path, bytes)
        self.path = path
        self.lockcount = 0

    def __enter__(self):
        """
        Obtain a lock for this object. This is usually done internaly
        by more productive functions. Manual intervention is only necessary,
        if several locks have to be obtained before an operation can be carried
        out. Note that locks have to be obtained in lexicographic order by native
        byte order (in particular captital letter before lower case letters).

        Acquiring this object multiple times will succeed, but you have to
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
            except OSError as e:
                if e.errno == errno.EEXIST:
                    logger.debug("lock %r is busy" % self.path)
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
        @type path: bytes
        @type filename: bytes
        """
        assert isinstance(path, bytes)
        assert isinstance(filename, bytes)
        self.path = path
        self.filename = filename

    def fullpath(self, prefix=b"", postfix=b""):
        """Construct a derived path based on the storage. The passed prefix is
        inserted between the base directory and the filename. The postfix is
        appended to the filename.
        @type prefix: bytes
        @type postfix: bytes
        @rtype: bytes
        """
        assert isinstance(prefix, bytes)
        assert isinstance(postfix, bytes)
        return os.path.join(self.path, prefix + self.filename + postfix)

    @property
    def lock(self):
        return LockDir(self.fullpath(prefix=b"#lock."))

    def store(self, content, user=None, message=b"store called", havelock=None):
        """
        Store the given contents; rcs file is create if it does not
        exist already.

        @type content: bytes or raw filelike 
        @param content: the content of the file
        @type message: bytes
        @type user: None or bytes
        """
        assert not isinstance(content, unicode)
        assert isinstance(message, bytes)
        if isinstance(content, bytes):
            content = io.BytesIO(content)
        logger.debug("storing %r" % self.fullpath())

        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock = gotlock)
            subprocess.check_call([b'co', b'-f', b'-q', b'-l', self.fullpath()],
                                  env=RCSENV)
            with open(self.fullpath(), "wb") as objfile:
                shutil.copyfileobj(content, objfile)
            args = [b'ci', b'-q', b'-f', b'-m%s' % message]
            if user is not None:
                args.append(b'-w%s' % user)
            args.append(self.fullpath())
            subprocess.check_call(args, env=RCSENV)

    def ensureexistence(self, havelock=None):
        if not os.path.exists(self.fullpath(postfix=b",v")):
            with havelock or self.lock:
                if not os.path.exists(self.fullpath(postfix=b",v")):
                    logger.debug("creating rcs file %r" % self.fullpath())
                    subprocess.check_call(["rcs", "-q", "-i", "-t-created by store",
                                           self.fullpath()], env=RCSENV)
                    with open(self.fullpath(), "wb"):
                        pass
                    subprocess.check_call(["ci", "-q", "-f",
                                           "-minitial, implicit, empty commit",
                                           self.fullpath()], env=RCSENV)

    def asrcs(self, havelock=None):
        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock=gotlock)
            with open(self.fullpath(postfix=b",v"), "rb") as f:
                content = f.read()
            return content

    def status(self, havelock=None):
        """
        @rtype: str
        """
        self.ensureexistence(havelock = havelock)
        result = rlogv(self.fullpath(postfix=b",v"))
        if result is None:
            result = rlogv(self.fullpath(prefix=b"RCS/", postfix=b",v"))
        return result

    def commitstatus(self, havelock=None):
        """
        Obtain information about the last change made to this storage object.
        @returns: a bytes-object dict with information about the head commit;
                  in particular, it will contain the keys b'revision', b'author',
                  and b'date'. All values are bytes, except for the b'date' key
                  which has a datetime object associated.
        """
        self.ensureexistence(havelock=havelock)
        return rloghead(self.fullpath(postfix=b",v"))

    def content(self, havelock=None):
        self.ensureexistence(havelock = havelock)
        logger.debug("retrieving content for %r" % self.fullpath())
        return check_output(["co", "-q", "-p", "-kb", self.fullpath()],
                            env=RCSENV)

    def startedit(self, havelock=None):
        """
        start editing a file (optimistic synchronisation)

        At dokuforge 2 we try optimistic synchronisation, i.e., we log (not lock)
        the version at which a user started editing and at the end just verify if
        that version is still the head revision.

        @returns: an opaque version string and the contents of the file
        @rtype: (bytes, str)
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

        @type version: bytes
        @param version: the opaque version string optained from startedit
                        when the user started editing the file
        @type newcontent: bytes
        @param newcontent: the new content, produced by the user starting from
                           the content at the provided version
        @type user: None or bytes
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
        assert isinstance(version, bytes)
        assert isinstance(newcontent, bytes)
        assert user is None or isinstance(user, bytes)
        validateRcsRevision(version)

        ## Transform text to Unix line ending
        newcontent = b"".join(map(b"%s\n".__mod__, newcontent.splitlines()))
        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock = gotlock)
            currentversion = self.status(havelock = gotlock)
            if currentversion == version:
                self.store(newcontent, user = user, havelock = gotlock)
                newversion = self.status(havelock = gotlock)
                return True, newversion, newcontent
            ## conflict
            # 1.) store in a branch
            logger.debug("storing conflict %r current=%r vs edited=%r" %
                         (self.fullpath(), currentversion, version))
            try:
                subprocess.check_call(["co", "-f", "-q", "-l%s" % version,
                                       self.fullpath()], env=RCSENV)
            except CalledProcessError:
                raise RcsUserInputError(u"specified rcs version does not exist",
                                        u"can only happen in hand-crafted requests")
            with open(self.fullpath(), "wb") as objfile:
                objfile.write(newcontent)
            args = ["ci", "-f", "-q", "-u"]
            args.append("-mstoring original edit conflicting with %s in a branch" % currentversion)
            if user is not None:
                args.append("-w%s" % user)
            args.append(self.fullpath())
            subprocess.check_call(args, env=RCSENV)
            # 2.) merge in head
            os.chmod(self.fullpath(), 0o600)
            subprocess.call(["rcsmerge", "-q", "-r%s" % version,
                             self.fullpath()]) # Note: non-zero exit status is
                                               # OK!
            with open(self.fullpath(), "rb") as objfile:
                mergedcontent = objfile.read()
            os.unlink(self.fullpath())
            # 3) return new state
            return False, currentversion, mergedcontent

    def timestamp(self, havelock=None):
        """
        @rtype: datetime
        """
        self.ensureexistence(havelock = havelock)
        ts = os.path.getmtime(self.fullpath(postfix=b",v"))
        ts = datetime.datetime.utcfromtimestamp(ts)
        return ts.replace(tzinfo=utc)

class CachingStorage(Storage):
    """
    A storage Object that caches the contents; useful if a lot
    of read is attemted
    """

    def __init__(self, path, filename):
        Storage.__init__(self, path, filename)
        self.cachedtime = epoch # Jan 1, 1970 -- way before the first dokuforge2 installation
        self.cachedvalue = ""

    def content(self, havelock=None):
        mtime = self.timestamp()
        if mtime == self.cachedtime:
            pass # content already up to date
        else:
            self.cachedtime = mtime
            self.cachedvalue = Storage.content(self)
        return self.cachedvalue
