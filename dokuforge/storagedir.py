import os.path
import re

try:
    unicode
except NameError:
    unicode = str

from dokuforge.storage import Storage
from dokuforge.view import LazyView
import dokuforge.common as common

class StorageDir:
    """Backend for manipulating file structures within a directory. It brings
    a few methods that C{Academy}s and C{Course}s have in common.
    """
    def __init__(self, obj):
        """
        @type obj: bytes or StorageDir
        """
        if isinstance(obj, StorageDir):
            obj = obj.path
        assert isinstance(obj, bytes)
        self.path = obj

    def getstorage(self, filename):
        """
        @type filename: bytes
        @param filename: passed to Storage as second param
        @rtype: Storage
        @returns: a Storage build from self.path and filename
        """
        assert isinstance(filename, bytes)
        return Storage(self.path, filename)

    def getcontent(self, filename, havelock=None):
        """
        @type filename: bytes
        @param filename: passed to Storage as second param
        @type havelock: None or LockDir
        @rtype: str
        @returns: the content of the Storage build from self.path and filename
        """
        return self.getstorage(filename).content(havelock)

    @property
    def name(self):
        """
        @rtype: bytes
        """
        return os.path.basename(self.path)

    @property
    def number(self):
        """
        A best guess of a number associated with this directory.

        @rtype: int
        """
        digits = re.compile("[^0-9]*([0-9]+)")
        basename = os.path.basename(self.path)
        m = digits.match(basename)
        if m is None:
            return 0
        return int(m.group(1))
        

    def gettitle(self):
        """
        @returns: contents of the "title" Storage
        @rtype: unicode
        """
        return self.getcontent(b"title").decode("utf8")

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
        self.getstorage(b"title").store(title.encode("utf8"))
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
