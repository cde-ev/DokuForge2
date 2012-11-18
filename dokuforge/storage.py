import datetime
import io
import logging
import os, errno
import shutil
import time
import subprocess
import re

from dokuforge.common import check_output, utc, epoch
from dokuforge.common import validateRcsRevision
from dokuforge.dfexceptions import RcsUserInputError, RcsError
from dokuforge.dfexceptions import FileDoesNotExist

logger = logging.getLogger(__name__)

RCSENV = os.environ.copy()
RCSENV["LC_ALL"] = "C"

def call_rcs(cmdline):
    """
    @type cmdline: [str]
    @rtype: str
    @returns: the content received on stdout
    @raises RcsError: if the process exits with a non-zero status
    """
    assert isinstance(cmdline, list)
    process = subprocess.Popen(cmdline, env=RCSENV, stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode:
        raise RcsError("failure invoking %r" % cmdline, stderr,
                       process.returncode)
    return stdout

def rlogv(filename):
    """
    Return the head revision of an rcs file

    (needed, as rlog -v is a FreeBSD extension)
    @type filename: bytes or None
    """
    # FIXME: maybe use proper exceptions to differentiate errors?
    assert isinstance(filename, bytes)
    logger.debug("rlogv: looking up revision for %r" % filename)
    try:
        with file(filename) as rcsfile:
            content = rcsfile.read()
    except IOError:
        return None
    m = re.match(r'^\s*head\s*([0-9.]+)\s*;', content)
    if m:
        return m.groups()[0]
    else:
        return None

rcsseparator='----------------------------' 

def rloghead(filename):
    """
    Get relevant information for the head revision of the given rcs file

    @type filename: bytes
    @returns: a str-object dict with information about the head commit; in particular,
              it will contain the keys 'revision', 'author', and 'date'.
              All values are str, except for the 'date' key which has a
              datetime object associated.
    @rtype: {str: object}
    @raises FileDoesNotExist:
    @raises RcsError:
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
    if revision is None:
        raise FileDoesNotExist(filename)
    answer['revision'] = revision
    rlog = call_rcs(["rlog", "-q", "-r%s" % revision, filename])
    lines = rlog.splitlines()
    try:
        while lines[0] != rcsseparator or lines[1].split()[0] != 'revision':
            lines.pop(0)
        lines.pop(0)
        lines.pop(0)
        stateline = lines.pop(0)
        params = stateline.split(';')
        for param in params:
            keyvalue = param.split(': ',1)
            if len(keyvalue) > 1:
                answer[keyvalue[0].lstrip()]=keyvalue[1]
    except IndexError:
        # as discussed above, the output format is an invariant for all rcs
        # implementations
        raise RcsError("failed to parse rcs-file, corrupted data: %s" % filename)
    try:
        answer["author"]
        answer["date"]
    except KeyError:
        # The rlog we used is not the rcs tool.
        raise RcsError("failed to parse rcs-file, missing data: %s" % filename)

    date = datetime.datetime.strptime(answer["date"], "%Y/%m/%d %H:%M:%S")
    answer["date"] = date.replace(tzinfo=utc)
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

        @raises RcsError:
        """
        if self.lockcount != 0:
            self.lockcount += 1
            return self
        while True: # FIXME: we should somehow timeout
            try:
                os.mkdir(self.path)
                self.lockcount = 1
                return self
            except OSError as e:
                if e.errno == errno.EEXIST:
                    logger.debug("lock %r is busy" % self.path)
                    time.sleep(0.2) # evertthing OK, someone else has the lock
                else:
                    errname = errno.errorcode.get(e.errno, str(e.errno))
                    raise RcsError("failed to lock %r with mkdir giving -%s" %
                                   (self.path, errname))

    def __exit__(self, _1, _2, _3):
        """
        @raises RcsError:
        """
        self.lockcount -= 1
        if self.lockcount == 0:
            try:
                os.rmdir(self.path)
            except OSError, e:
                errname = errno.errorcode.get(e.errno, str(e.errno))
                raise RcsError("failed to unlock %r with rmdir giving -%s" %
                               (self.path, errname))


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

    def store(self, content, user=None, message="store called", havelock=None):
        """
        Store the given contents; rcs file is create if it does not
        exist already.

        @type content: bytes or raw filelike 
        @param content: the content of the file
        @type message: str
        @raises IOError:
        @raises RcsError:
        """
        if isinstance(content, basestring):
            assert isinstance(content, bytes)
            content = io.BytesIO(content)
        logger.debug("storing %r" % self.fullpath())

        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock = gotlock)
            ## we ensured the existence of the file, hence the call may not fail
            call_rcs(["co", "-f", "-q", "-l", self.fullpath()])
            objfile = file(self.fullpath(), mode = "w")
            shutil.copyfileobj(content, objfile)
            objfile.close()
            args = ["ci", "-q", "-f", "-m%s" % message]
            if user is not None:
                args.append("-w%s" % user)
            args.append(self.fullpath())
            call_rcs(args)

    def ensureexistence(self, havelock=None):
        """
        @raises RcsError:
        """
        if not os.path.exists(self.fullpath(postfix=b",v")):
            with havelock or self.lock:
                if not os.path.exists(self.fullpath(postfix=b",v")):
                    logger.debug("creating rcs file %r" % self.fullpath())
                    # These calls can only fail for reasons like
                    # disk full, permision denied -- all cases where
                    # dokuforge is not installed correctly
                    call_rcs(["rcs", "-q", "-i", "-t-created by store",
                              self.fullpath()])
                    try:
                        file(self.fullpath(), mode = "w").close()
                    except IOError, err:
                        raise RcsError("failed to touch %r: %s" %
                                       (self.fullpath(), str(err)))
                    call_rcs(["ci", "-q", "-f",
                              "-minitial, implicit, empty commit",
                              self.fullpath()])

    def asrcs(self, havelock=None):
        """
        @raises IOError:
        @raises RcsError:
        """
        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock=gotlock)
            f = file(self.fullpath(postfix=b",v"), mode="r")
            content = f.read()
            f.close()
            return content

    def status(self, havelock=None):
        """
        @rtype: str or None
        @raises RcsError:
        """
        self.ensureexistence(havelock = havelock)
        result = rlogv(self.fullpath(postfix=b",v"))
        if result is None:
            result = rlogv(self.fullpath(prefix=b"RCS/", postfix=b",v"))
        return result

    def commitstatus(self, havelock=None):
        """
        Obtain information about the last change made to this storage object.
        @returns: a str-object dict with information about the head commit;
                  in particular, it will contain the keys 'revision', 'author',
                  and 'date'. All values are str, except for the 'date' key
                  which has a datetime object associated.
        @raises RcsError:
        """
        self.ensureexistence(havelock=havelock)
        try:
            status = rloghead(self.fullpath(postfix=b",v"))
        except FileDoesNotExist:
            # we just ensured the existence
            raise RcsError("failed to get commitstatus, rcs-file %s vanished" %
                           self.fullpath(postfix=b",v"))
        return status

    def content(self, havelock=None):
        """
        @raises RcsError:
        """
        self.ensureexistence(havelock = havelock)
        logger.debug("retrieving content for %r" % self.fullpath())
        # We ensured the existence of the file; hence the call can only fail
        # if rcs is not installed properly and/or filepermissions are set
        # incorrectly -- in other words, if df is not installed correctly
        return call_rcs(["co", "-q", "-p", "-kb", self.fullpath()])

    def startedit(self, havelock=None):
        """
        start editing a file (optimistic synchronisation)

        At dokuforge 2 we try optimistic synchronisation, i.e., we log (not lock)
        the version at which a user started editing and at the end just verify if
        that version is still the head revision.

        @returns: an opaque version string and the contents of the file
        @rtype: (str, str)
        @raises RcsError:
        """
        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock = gotlock)
            status = self.status(havelock = gotlock)
            content = self.content(havelock = gotlock)
            # FIXME: explain why status is not None
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
        @rtype: (bool, str, str)
        @raises OSError:
        @raises IOError:
        @raises RcsUserInputError

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
        newcontent = b"\n".join(newcontent.splitlines()) + b"\n"
        with havelock or self.lock as gotlock:
            self.ensureexistence(havelock = gotlock)
            currentversion = self.status(havelock = gotlock)
            assert currentversion is not None
            if currentversion == version:
                self.store(newcontent, user = user, havelock = gotlock)
                newversion = self.status(havelock = gotlock)
                return True, newversion, newcontent
            ## conflict
            # 1.) store in a branch
            logger.debug("storing conflict %r current=%r vs edited=%r" %
                         (self.fullpath(), currentversion, version))
            try:
                call_rcs(["co", "-f", "-q", "-l%s" % version,
                          self.fullpath()])
            except RcsError, error:
                # FIXME: verify that the passed revision is indeed rejected
                # Otherwise we may be hiding real errors. Looking at
                # error.stderr might help here.
                raise RcsUserInputError()
            objfile = file(self.fullpath(), mode = "w")
            objfile.write(newcontent)
            objfile.close()
            args = ["ci", "-f", "-q", "-u"]
            args.append("-mstoring original edit conflicting with %s in a branch" % currentversion)
            if user is not None:
                args.append("-w%s" % user)
            args.append(self.fullpath())
            call_rcs(args)
            # 2.) merge in head
            os.chmod(self.fullpath(), 0o600)
            try:
                call_rcs(["rcsmerge", "-q", "-r%s" % version, self.fullpath()])
            except RcsError, error:
                # Note: non-zero exit status is OK!
                # FIXME: can we distinguish merge conflicts from other errors
                # using error.stderr or error.code?
                pass
            objfile = file(self.fullpath(), mode = "r")
            mergedcontent = objfile.read()
            objfile.close()
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
        # inherit doc string from Storage.__init__
        Storage.__init__(self, path, filename)
        self.cachedtime = epoch # Jan 1, 1970 -- way before the first dokuforge2 installation
        self.cachedvalue = ""

    def content(self, havelock=None):
        """
        @raises RcsError:
        """
        self.ensureexistence(havelock = havelock)
        mtime = self.timestamp()
        if mtime == self.cachedtime:
            pass # content already up to date
        else:
            self.cachedtime = mtime
            self.cachedvalue = Storage.content(self)
        return self.cachedvalue
