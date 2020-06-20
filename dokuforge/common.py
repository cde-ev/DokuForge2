# -*- coding: utf-8 -*-

import configparser
import io
import random
import subprocess
import re
import os
import tarfile
import datetime
import calendar
import typing

sysrand = random.SystemRandom()


def randstring(n: int = 6) -> str:
    """
    @returns: random string of length n
    """
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(sysrand.choice(chars) for x in range(n))


def strtobool(s: str) -> bool:
    """
    @returns: Boolean version of s
    """
    return s in ("True", "true", "t")


class CheckError(Exception):
    def __init__(self, msg: str, exp: str) -> None:
        Exception.__init__(self, msg)
        assert isinstance(msg, str)
        assert isinstance(exp, str)
        self.message = msg
        self.explanation = exp
    def __str__(self):
        return self.message

epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def validateGroupstring(groupstring: str, allgroups) -> None:
    """
    check whether groupstring contains a valid set of groups. This means
    it may not be empty and it may not contain non-existent groups. If a
    check fails a CheckError is raised.

    @param groupstring: contains groups seperated by whitespace
    @raises CheckError:
    """
    assert isinstance(groupstring, str)
    validateGroups(groupstring.split(), allgroups)


def validateGroups(groups: typing.List[str], allgroups) -> None:
    """
    check whether list of groups is a valid set of groups. This means
    it may not be empty and it may not contain non-existent groups. If a
    check fails a CheckError is raised.

    @param groups: a list of groups to validate
    @raises CheckError:
    """
    assert all(isinstance(g, str) for g in groups)
    if len(groups) == 0:
        raise CheckError("Keine Gruppen gefunden!",
                         "Jede Akademie muss mindestens einer Gruppe angehören. Bitte korrigieren und erneut versuchen.")
    for g in groups:
        if g not in allgroups:
            raise CheckError("Nichtexistente Gruppe gefunden!",
                             "Bitte korrigieren und erneut versuchen.")


def validateTitle(title: str) -> None:
    """
    check whether the title is valid, this means nonempty. If not raise
    a CheckError exception.

    @param title: title to check
    @raises CheckError:
    """
    assert isinstance(title, str)
    if title == "":
        raise CheckError("Leerer Titel!",
                         "Der Titel darf nicht leer sein.")
    if re.match('^[ \t]*$', title) is not None:
        raise CheckError("Leerer Titel!",
                         "Der Titel darf nicht nur aus Leerzeichen bestehen.")


def validateBlobLabel(label: str) -> None:
    """
    check whether a label for a blob is valid. This means matching a certain
    regexp. Otherwise raise a CheckError.

    @param label: label to check
    @raises CheckError:
    """
    assert isinstance(label, str)
    if re.match('^[a-z0-9]{1,200}$', label) is None:
        raise CheckError("Kürzel nicht wohlgeformt!",
                         "Das Kürzel darf lediglich Kleinbuchstaben [a-z] und Ziffern [0-9] enthalten, nicht leer sein und nicht mehr als 200 Zeichen enthalten.")


def validateBlobComment(comment: str) -> None:
    """
    check whether a label for a blob is valid. This means beeing
    nonempty. Otherwise raise a CheckError.

    @param comment: comment to check
    @raises CheckError:
    """
    assert isinstance(comment, str)
    if comment == "":
        raise CheckError("Keine Bildunterschrift gefunden!",
                         "Bitte eine Bildunterschrift eingeben und erneut versuchen.")


class InvalidBlobFilename(CheckError):
    pass


def validateBlobFilename(filename: bytes) -> None:
    """
    check whether a filename for a blob is valid. This means matching a certain
    regexp. Otherwise raise a CheckError.

    @param filename: filename to check
    @raises InvalidBlobFilename:
    """
    assert isinstance(filename, bytes)
    if re.match(b'^[a-zA-Z0-9][-a-zA-Z0-9_.]{1,200}[a-zA-Z0-9]$', filename) is None:
        raise InvalidBlobFilename("Dateiname nicht wohlgeformt!",
                                  "Bitte alle Sonderzeichen aus dem Dateinamen entfernen und erneut versuchen. Der Dateinahme darf nicht mehr als 200 Zeichen enthalten.")


def validateInternalName(name: str) -> None:
    """
    check whether a name is accepted for representing something on disk, i.e.
    for the internal representation. This means matching a certain
    regexp. Otherwise raise a CheckError.

    @param name: name to check
    @raises CheckError:
    """
    assert isinstance(name, str)
    if re.match('^[a-zA-Z][-a-zA-Z0-9]{0,199}$', name) is None:
        raise CheckError("Interner Name nicht wohlgeformt!",
                         "Der Name darf lediglich Klein-, Großbuchstaben, Ziffern sowie Bindestriche enthalten, muss mit einem Buchstaben beginnen und darf nicht mehr als 200 Zeichen enthalten.")


def validateNonExistence(path: bytes, name: bytes) -> None:
    """
    check whether a name is already in use as internal representation, if so
    raise a CheckError. This also checks for additional rcs file extensions.

    @param name: name to check for existence
    @param path: base path in which to check for the name
    @raises CheckError:
    """
    assert isinstance(name, bytes)
    assert isinstance(path, bytes)
    if os.path.exists(os.path.join(path, name)) or \
           os.path.exists(os.path.join(path, name + b",v")):
        raise CheckError("Interner Name bereits vergeben!",
                         "Wähle einen anderen Namen.")


def validateExistence(path: bytes, name: bytes) -> None:
    """
    check whether a name exsits. If not raise a CheckError.

    @param name: name to check for existence
    @param path: base path in which to check for the name
    @raises CheckError:
    """
    assert isinstance(name, bytes)
    assert isinstance(path, bytes)
    if not os.path.exists(os.path.join(path, name)):
        raise CheckError("Interner Name existiert nicht!",
                         "Bitte den Namen korrigieren.")

def sanitizeBlobFilename(name):
    return "einedatei.dat"


def validateUserConfig(config: str) -> None:
    """
    Try parsing the supplied config with ConfigParser. If this fails
    raise a CheckError saying so.
    """
    assert isinstance(config, str)
    parser = configparser.ConfigParser()
    try:
        parser.read_string(config)
    except configparser.ParsingError as err:
        raise CheckError("Es ist ein allgemeiner Parser-Fehler aufgetreten!",
                         "Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)
    try:
        for name in parser.sections():
            for perm in parser.get(name, 'permissions').split(','):
                if len(perm.strip().split(' ')) != 2:
                    raise CheckError(
                        "Fehler in Permissions.",
                        "Das Recht '%s' für '%s' ist nicht wohlgeformt." %
                        (perm, name))
            parser.get(name, 'status')
            parser.get(name, 'password')
    except configparser.NoOptionError as err:
        raise CheckError("Es fehlt eine Angabe!",
                         "Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)


def validateGroupConfig(config: str) -> None:
    """
    Try parsing the supplied config with ConfigParser. If this fails
    raise a CheckError saying so.
    """
    assert isinstance(config, str)
    parser = configparser.ConfigParser()
    try:
        parser.read_string(config)
    except configparser.Error as err:
        raise CheckError("Es ist ein allgemeiner Parser-Fehler aufgetreten!",
                         "Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)
    try:
        for name in parser.sections():
            parser.get(name, 'title')
    except configparser.NoOptionError as err:
        raise CheckError("Es fehlt eine Angabe!",
                         "Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)

class RcsUserInputError(CheckError):
    pass


def validateRcsRevision(versionnumber: bytes) -> None:
    """
    Check if versionnumber is a syntactically well-formed rcs version number

    @raises RcsUserInputError:
    """
    assert isinstance(versionnumber, bytes)
    if re.match(br'^[1-9][0-9]{0,10}\.[1-9][0-9]{0,10}(\.[1-9][0-9]{0,10}\.[1-9][0-9]{0,10}){0,5}$',
                versionnumber) is None:
        raise RcsUserInputError("rcs version number syntactically malformed",
                                "can only happen in hand-crafted requests")

class TarWriter:
    def __init__(self, gzip=False) -> None:
        self.io = io.BytesIO()
        # tarfile requires the use of decoded strings, so choose any encoding
        # that will never fail decoding arbitrary bytes. In particular choose
        # the encoding used by wsgi: iso8859-1. Note that we do not rely on
        # the decoded data to carry any meaning beyond being able to encode it.
        if gzip:
            self.tar = tarfile.open(mode="w|gz", fileobj=self.io,
                                    encoding="iso8859-1")
        else:
            self.tar = tarfile.open(mode="w|", fileobj=self.io,
                                    encoding="iso8859-1")
        self.dirs = []

    @property
    def prefix(self):
        return "".join(map(lambda s: s + "/", self.dirs))

    def pushd(self, dirname: bytes) -> None:
        """Push a new directory on the directory stack. Further add* calls will
        place their files into this directory. The operation must be reverted
        using popd before close is called. The directory name must not contain
        a slash.
        """
        assert isinstance(dirname, bytes)
        assert b"/" not in dirname
        self.dirs.append(dirname.decode("iso8859-1"))

    def popd(self) -> str:
        """Pop the topmost directory off the directory stack.
        @returns: the basename popped
        """
        assert self.dirs
        return self.dirs.pop()

    def read(self):
        data = self.io.getvalue()
        self.io.seek(0)
        self.io.truncate(0)
        return data

    def addChunk(self, name: bytes, content: bytes,
                 lastchanged: datetime.datetime) -> bytes:
        """
        Add a file with given content and return some tar content generated
        along the way.
        """
        assert isinstance(name, bytes)
        assert isinstance(content, bytes)
        name = name.decode("iso8859-1")
        assert isinstance(lastchanged, datetime.datetime)

        info = tarfile.TarInfo(self.prefix + name)
        info.size = len(content)
        info.mtime = calendar.timegm(lastchanged.utctimetuple())
        self.tar.addfile(info, io.BytesIO(content))
        return self.read()

    def addFileChunk(self, name: bytes, filename: bytes) -> bytes:
        """
        Add a regular file with given (tar) name and given (filesystem)
        filename and return some tar content generated along the way.
        """
        assert isinstance(name, bytes)
        name = name.decode("iso8859-1")
        info = tarfile.TarInfo(self.prefix + name)
        with open(filename, "rb") as infile:
            infile.seek(0, 2)
            info.size = infile.tell()
            info.mtime = os.path.getmtime(filename)
            infile.seek(0)
            self.tar.addfile(info, infile)
        return self.read()

    def addDirChunk(self, name: bytes, dirname: bytes, excludes=[]):
        """
        Recursively add a filesystem directory dirname using the given name.
        Only regular files and directories are considered. Any basename that
        is contained in excludes is left out. The tar content generated along
        the way is returned as a bytes iterator.
        @param excludes: an object that provides __contains__
        """
        self.pushd(name)
        try:
            for entry in os.listdir(dirname):
                if entry in excludes:
                    continue
                fullpath = os.path.join(dirname, entry)
                if os.path.isfile(fullpath):
                    yield self.addFileChunk(entry, fullpath)
                elif os.path.isdir(fullpath):
                    for chunk in self.addDirChunk(entry, fullpath,
                                                  excludes=excludes):
                        yield chunk
        finally:
            self.popd()

    def close(self) -> bytes:
        """
        Close the TarWriter and return the remaining content.
        """
        assert not self.dirs
        self.tar.close()
        return self.io.getvalue()


def findlastchange(changes: typing.List[typing.Dict[str, typing.Any]]) -> \
        typing.Dict[str, typing.Any]:
    """
    Given a list of rcs revision informations find the newest change.

    @param changes: list of dictionary containing the keys 'author',
                    'revision' and 'date'
    @returns: returns the dictionary with the latest date
    """
    return max(changes + [{'author': 'unkown', 'revision': '?',
                           'date': epoch}], key=lambda x: x["date"])
