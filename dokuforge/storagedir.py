import os.path

from dokuforge.storage import Storage
from dokuforge.view import LazyView
import dokuforge.common as common
from datetime import datetime

class StorageDir:
    """Backend for manipulating file structures within a directory. It brings
    a few methods that C{Academy}s and C{Course}s have in common.
    """
    def __init__(self, obj):
        """
        @type obj: str or StorageDir
        """
        if isinstance(obj, StorageDir):
            obj = obj.path
        assert isinstance(obj, str)
        self.path = obj

    def getstorage(self, filename):
        """
        @type filename: str
        @param filename: passed to Storage as second param
        @rtype: Storage
        @returns: a Storage build from self.path and filename
        """
        assert isinstance(filename, str)
        return Storage(self.path, filename)

    def getcontent(self, filename, havelock=None):
        """
        @type filename: str
        @param filename: passed to Storage as second param
        @type havelock: None or LockDir
        @rtype: str
        @returns: the content of the Storage build from self.path and filename
        """
        return self.getstorage(filename).content(havelock)

    @property
    def name(self):
        """
        @rtype: str
        """
        return os.path.basename(self.path)

    def gettitle(self):
        """
        @returns: contents of the "title" Storage
        @rtype: unicode
        """
        return self.getcontent("title").decode("utf8")

    def settitle(self, title):
        """
        Updates the "title" Storage.

        @param title: display name of the academy
        @type title: unicode
        @rtype: bool
        @returns: True when successful
        @raises CheckError: if the user input is malformed.
        """
        assert isinstance(title, unicode)
        common.validateTitle(title)
        self.getstorage("title").store(title.encode("utf8"))
        return True

    def view(self, extrafunctions=dict()):
        """
        @type extrafunctions: {str: function}
        @param extrafunctions: the dict passed to LazyView is updated with
            this dict
        @rtype: LazyView
        @returns: a mapping providing the keys name(str) and title(unicode) as
            well as the keys from extrafunctions
        """
        functions = dict(
            name=lambda:self.name,
            title=self.gettitle)
        functions.update(extrafunctions)
        return LazyView(functions)

    def calculatelastchange(self, infos):
        lastchange = {'author': u'unkown', 'revision' : u'?', 'date' : u'1970/01/01 00:00:00'}
        compare = datetime.strptime(lastchange['date'], "%Y/%m/%d %H:%M:%S")
        for x in infos:
            date =  datetime.strptime(x['date'], "%Y/%m/%d %H:%M:%S")
            if date > compare:
                lastchange = x
                compare = datetime.strptime(lastchange['date'], "%Y/%m/%d %H:%M:%S")
        return lastchange

    def calculatetimestamp(self, timestamps):
        timestamp = -1
        for x in timestamps:
            if x > timestamp:
                timestamp = x
        return timestamp
