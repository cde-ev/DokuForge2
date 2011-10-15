import os, errno
import io
import time
import subprocess

class Storage(object):
    def __init__(self,path,filename):
        """
        A simple storage unit is described by a directory and the basename
        of a file in this direcotry. With the filename is also associated
        #lock.filename and filename,v as well as any rcs internal locks
        associated with it.
        """
        self.path=path
        self.filename=filename

    def fullpath(self, formatstr="%s"):
        """Join self.path with formatstr % self.filename.
        @type formatstr: str
        @param formatstr: format string that takes exactly one %s
        @rtype: str
        """
        return os.path.join(self.path, formatstr % self.filename)

    def getlock(self):
        """
        Obtain a lock for this Storage object. This is usually done internaly
        by more productive funcitons. Manual intervention is only necessary,
        if several locks have to be obtained before an operation can be carried
        out. Note that locks have to be obtained in lexicographic order by native
        byte order (in particular captital letter before lower case letters).

        If a lock is obtained manually, the productive functions of this class
        have to be informed aboutthis by setting the named argument havelock to True.
        """
        while True:
            try:
                os.mkdir(self.fullpath("#lock.%s"))
                return
            except OSError, e:
                if e.errno==errno.EEXIST:
                    time.sleep(0.2) # evertthing OK, someone else has the lock
                else:
                    raise # something else went wrong

    def releaselock(self):
        os.rmdir(self.fullpath("#lock.%s"))
    
    def store(self,content,user=None,message="store called",havelock=False):
        """
        Store the given contents; rcs file is create if it does not
        exist already.

        @param content: the content of the file as str-object
        """
        if not havelock:
            self.getlock() 
        try:
            self.ensureexistence(havelock=True)
            subprocess.check_call(["co", "-f", "-q", "-l", self.fullpath()])
            objfile = file(self.fullpath(), mode="w")
            objfile.write(content)
            objfile.close()
            args = ["ci","-q","-f","-m%s" % message]
            if user is not None:
                args.append("-w%s" % user)
            args.append(self.fullpath())
            subprocess.check_call(args)
        finally:
            if not havelock:
                self.releaselock()
                
    def ensureexistence(self,havelock=False):
        if not os.path.exists(self.fullpath("%s,v")):
            if not havelock:
                self.getlock() 
            try:
                subprocess.check_call(["rcs", "-q", "-i", "-t-created by store",
                                       self.fullpath()])
                objfile = file("%s/%s" % (self.path,self.filename), mode="w")
                objfile.close()
                subprocess.check_call(["ci","-q","-f","-minitial, implicit, empty commit", 
                                       self.fullpath()])
            finally:
                if not havelock:
                    self.releaselock()

    def status(self,havelock=False):
        self.ensureexistence(havelock=havelock)
        return subprocess.check_output(["rlog", "-v", self.fullpath()]) \
                .split()[1]

    def content(self, havelock=False):
        self.ensureexistence(havelock=havelock)
        return subprocess.check_output(["co", "-q", "-p", "-kb",
                                        self.fullpath()])

    def startedit(self,havelock=False):
        """
        start editing a file (optimistic synchronisation)

        At dokuforge 2 we try optimistic synchronisation, i.e., we log (noch lock)
        the version at which a user started editing and at the end just verify if
        that version is still the head revision.

        @returns: an opaque version string and the contents of the file
        """
        self.ensureexistence()
        if not havelock:
            self.getlock() 
        try:
            status=self.status(havelock=True)
            content=self.content(havelock=True)
            return status, content
        finally:
            if not havelock:
                self.releaselock()

            
    def endedit(self,version,newcontent,user=None,havelock=False):
        """
        Store new contents in a safe way.

        Check if the version provided is still up to date. If so,
        store it as new head revision. If not, store it to a branch,
        merge with new head revision and return new version content pair.

        @param version: the opaque version string optained from startedit
                        when the user started editing the file
        @param newcontent: the new content, produced by the user starting from
                           the content at the provided version
        @returns: a triple (ok,newversion,mergedcontent) where ok is boolen with value
                  True if the save was sucessfull (if not, a merge has to be done manually),
                  and (newversion,mergedcontent) is a state for further editing that can be
                  used as if obtained from startedit
        """
        self.ensureexistence()
        if not havelock:
            self.getlock() 
        try:
            currentversion = self.status(havelock=True)
            if currentversion == version:
                self.store(newcontent, user=user, havelock=True)
                newversion = self.status(havelock=True)
                return True,newversion,newcontent
            ## conflict
            # 1.) store in a branch
            subprocess.check_call(["co", "-f", "-q", "-l%s" % version,
                                   self.fullpath()])
            objfile = file(self.fullpath(), mode="w")
            objfile.write(newcontent)
            objfile.close()
            args=["ci","-f","-q","-u"]
            args.append("-mstoring original edit conflictig with %s in a branch" % currentversion)
            if user is not None:
                args.append("-w%s" % user)
            args.append
            args.append(self.fullpath())
            subprocess.check_call(args)
            # 2.) merge in head
            os.chmod(self.fullpath(), 0600)
            subprocess.call(["rcsmerge", "-q", "-r%s" % version,
                             self.fullpath()]) # Note: non-zero exit status is OK!
            objfile = file(self.fullpath(), mode="r")
            mergedcontent = objfile.read()
            objfile.close()
            os.unlink(self.fullpath())
            # 3) return new state
            return False,currentversion,mergedcontent
        finally:
            if not havelock:
                self.releaselock()

