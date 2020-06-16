import os.path
import re
import typing

from dokuforge.storage import LockDir, Storage
from dokuforge.view import LazyView
import dokuforge.common as common

class StorageDir:
    """Backend for manipulating file structures within a directory. It brings
    a few methods that C{Academy}s and C{Course}s have in common.
    """
    def __init__(self, obj: typing.Union[bytes, "StorageDir"]) -> None:
        if isinstance(obj, StorageDir):
            obj = obj.path
        assert isinstance(obj, bytes)
        self.path = obj

    def getstorage(self, filename: bytes) -> Storage:
        """
        @param filename: passed to Storage as second param
        @returns: a Storage build from self.path and filename
        """
        assert isinstance(filename, bytes)
        return Storage(self.path, filename)

    def getcontent(self, filename: bytes,
                   havelock: typing.Optional[LockDir] = None) -> str:
        """
        @param filename: passed to Storage as second param
        @returns: the content of the Storage build from self.path and filename
        """
        return self.getstorage(filename).content(havelock)

    @property
    def name(self) -> bytes:
        return os.path.basename(self.path)

    def rawExportIterator(self, tarwriter: common.TarWriter) -> \
            typing.Iterable[str]:
        """
        @returns: a tar ball containing the full internal information about
                this storage dir
        """
        for chunk in tarwriter.addDirChunk(self.name, self.path):
            yield chunk

    @property
    def number(self) -> int:
        """
        A best guess of a number associated with this directory.
        """
        digits = re.compile(b"[^0-9]*([0-9]+)")
        basename = os.path.basename(self.path)
        m = digits.match(basename)
        if m is None:
            return 0
        return int(m.group(1))

    def gettitle(self) -> str:
        """
        @returns: contents of the "title" Storage
        """
        return self.getcontent(b"title").decode("utf8")

    def settitle(self, title: str) -> bool:
        """
        Updates the "title" Storage.

        @param title: display name of the academy
        @returns: True when successful
        @raises CheckError: if the user input is malformed.
        """
        assert isinstance(title, str)
        common.validateTitle(title)
        self.getstorage(b"title").store(title.encode("utf8"))
        return True

    def view(self, extrafunctions=dict()) -> LazyView:
        """
        @type extrafunctions: {str: function}
        @param extrafunctions: the dict passed to LazyView is updated with
            this dict
        @returns: a mapping providing the keys name(bytes) and
            title(str) as well as the keys from extrafunctions
        """
        functions = dict(
            name=lambda:self.name,
            title=self.gettitle)
        functions.update(extrafunctions)
        return LazyView(functions)
