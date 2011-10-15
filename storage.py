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

    def getlock(self):
        """
        Obtain a lock for this Storage object. This is usually done internaly
        by more productive funcitons. Manual intervention is only necessary,
        if several locks have to be obtained before an operation can be carried
        out. Note that locks have to be obtained in lexicographic order.

        If a lock is obtained manually, the productive functions of this class
        have to be informed aboutthis by setting the named argument havelock to True.
        """
        while True:
            try:
                os.mkdir("%s/#lock.%s" % (self.path, self.filename))
                return
            except OSError, e:
                if e.errno==errno.EEXIST:
                    time.sleep(0.2) # evertthing OK, someone else has the lock
                else:
                    raise # something else went wrong

    def releaselock(self):
        os.rmdir("%s/#lock.%s" % (self.path, self.filename))
    
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
            subprocess.check_call(["rcs","-q","-l","%s/%s" % (self.path, self.filename)])
            objfile = file("%s/%s" % (self.path,self.filename), mode="w")
            objfile.write(content)
            objfile.close()
            args = ["ci","-q","-f","-m%s" % message]
            if user is not None:
                args.append("-w%s" % user)
            args.append("%s/%s" % (self.path, self.filename))
            subprocess.check_call(args)
        finally:
            if not havelock:
                self.releaselock()
                
    def ensureexistence(self,havelock=False):
        if not os.path.exists("%s/%s,v" % (self.path,self.filename)):
            if not havelock:
                self.getlock() 
                try:
                    subprocess.check_call(["rcs","-q","-i","-t-created by store", "%s/%s" % (self.path, self.filename)])
                    objfile = file("%s/%s" % (self.path,self.filename), mode="w")
                    objfile.close()
                    subprocess.check_call(["ci","-q","-f","-minitial, implicit, empty commit", 
                                           "%s/%s" % (self.path, self.filename)])
                finally:
                    if not havelock:
                        self.releaselock()

    def status(self,havelock=False):
        self.ensureexistence(havelock=havelock)
        return subprocess.check_output(["rlog","-v","%s/%s" % (self.path, self.filename)]).split()[1]

    def content(self, havelock=False):
        self.ensureexistence(havelock=havelock)
        return subprocess.check_output(["co","-q","-p","%s/%s" % (self.path, self.filename)])

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

            
