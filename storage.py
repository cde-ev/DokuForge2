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
        """
        if not havelock:
            self.getlock() 
        try:
            if os.path.exists("%s/%s,v" % (self.path,self.filename)):
                subprocess.call(["rcs","-l","%s/%s" % (self.path, self.filename)])
            else:
                subprocess.call(["rcs","-i","-t-created by store", "%s/%s" % (self.path, self.filename)])
            objfile = io.open("%s/%s" % (self.path,self.filename), mode="w")
            objfile.write(content)
            objfile.close()
            args = ["ci","-q","-f","-m%s" % message]
            if user is not None:
                args.append("-u%s" % user)
            args.append("%s/%s" % (self.path, self.filename))
            subprocess.call(args)
        finally:
            if not havelock:
                self.releaselock()
