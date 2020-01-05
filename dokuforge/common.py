# -*- coding: utf-8 -*-

import io
import random
import subprocess
import re
import os
try:
    import ConfigParser as configparser
    from ConfigParser import SafeConfigParser as ConfigParser
except ImportError:
    import configparser
    from configparser import ConfigParser
import tarfile
import datetime
import calendar

try:
    check_output = subprocess.check_output
except AttributeError:
    def check_output(cmdline, **kwargs):
        proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, **kwargs)
        output, _ = proc.communicate()
        if proc.returncode:
            raise subprocess.CalledProcessError()
        return output

try:
    unicode
except NameError:
    unicode = str

sysrand = random.SystemRandom()

def randstring(n=6):
    """
    @returns: random string of length n
    @type n: int
    @rtype: str
    """
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(sysrand.choice(chars) for x in range(n))

def strtobool(s):
    """
    @returns: Boolean version of s
    @type s: unicode
    @rtype: bool
    """
    return s in (u"True", u"true", u"t")

class CheckError(Exception):
    def __init__(self, msg, exp):
        Exception.__init__(self, msg)
        assert isinstance(msg, unicode)
        assert isinstance(exp, unicode)
        self.message = msg
        self.explanation = exp
    def __str__(self):
        return self.message

class UTC(datetime.tzinfo):
    """UTC implementation taken from the Python documentation"""
    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return datetime.timedelta(0)
utc = UTC()
epoch = datetime.datetime(1970, 1, 1, tzinfo=utc)

def validateGroupstring(groupstring, allgroups):
    """
    check whether groupstring contains a valid set of groups. This means
    it may not be empty and it may not contain non-existent groups. If a
    check fails a CheckError is raised.

    @type groupstring: unicode
    @param groupstring: contains groups seperated by whitespace
    @raises CheckError:
    """
    assert isinstance(groupstring, unicode)
    validateGroups(groupstring.split(), allgroups)


def validateGroups(groups, allgroups):
    """
    check whether list of groups is a valid set of groups. This means
    it may not be empty and it may not contain non-existent groups. If a
    check fails a CheckError is raised.

    @type groups: [unicode]
    @param groups: a list of groups to validate
    @raises CheckError:
    """
    assert all(isinstance(g, unicode) for g in groups)
    if len(groups) == 0:
        raise CheckError(u"Keine Gruppen gefunden!",
                         u"Jede Akademie muss mindestens einer Gruppe angehören. Bitte korrigieren und erneut versuchen.")
    for g in groups:
        if g not in allgroups:
            raise CheckError(u"Nichtexistente Gruppe gefunden!",
                             u"Bitte korrigieren und erneut versuchen.")

def validateTitle(title):
    """
    check whether the title is valid, this means nonempty. If not raise
    a CheckError exception.

    @type title: unicode
    @param title: title to check
    @raises CheckError:
    """
    assert isinstance(title, unicode)
    if title == u"":
        raise CheckError(u"Leerer Titel!",
                         u"Der Titel darf nicht leer sein.")
    if re.match(u'^[ \t]*$', title) is not None:
        raise CheckError(u"Leerer Titel!",
                         u"Der Titel darf nicht nur aus Leerzeichen bestehen.")

def validateBlobLabel(label):
    """
    check whether a label for a blob is valid. This means matching a certain
    regexp. Otherwise raise a CheckError.

    @type label: unicode
    @param label: label to check
    @raises CheckError:
    """
    assert isinstance(label, unicode)
    if re.match(u'^[a-z0-9]{1,200}$', label) is None:
        raise CheckError(u"Kürzel nicht wohlgeformt!",
                         u"Das Kürzel darf lediglich Kleinbuchstaben [a-z] und Ziffern [0-9] enthalten, nicht leer sein und nicht mehr als 200 Zeichen enthalten.")

def validateBlobComment(comment):
    """
    check whether a label for a blob is valid. This means beeing
    nonempty. Otherwise raise a CheckError.

    @type comment: unicode
    @param comment: comment to check
    @raises CheckError:
    """
    assert isinstance(comment, unicode)
    if comment == u"":
        raise CheckError(u"Keine Bildunterschrift gefunden!",
                         u"Bitte eine Bildunterschrift eingeben und erneut versuchen.")

class InvalidBlobFilename(CheckError):
    pass

def validateBlobFilename(filename):
    """
    check whether a filename for a blob is valid. This means matching a certain
    regexp. Otherwise raise a CheckError.

    @type filename: bytes
    @param filename: filename to check
    @raises InvalidBlobFilename:
    """
    assert isinstance(filename, bytes)
    if filename == u'':
        raise InvalidBlobFilename(u"Dateiname ist leer!",
                                  u"Bitte und erneut versuchen und tatsächlich eine Datei hochladen.")
    elif re.match(b'^[a-zA-Z0-9][-a-zA-Z0-9_.]{1,200}[a-zA-Z0-9]$', filename) is None:
        raise InvalidBlobFilename(u"Dateiname nicht wohlgeformt!",
                                  u"Bitte alle Sonderzeichen aus dem Dateinamen entfernen und erneut versuchen. Der Dateinahme darf nicht mehr als 200 Zeichen enthalten.")

def validateInternalName(name):
    """
    check whether a name is accepted for representing something on disk, i.e.
    for the internal representation. This means matching a certain
    regexp. Otherwise raise a CheckError.

    @type name: unicode
    @param name: name to check
    @raises CheckError:
    """
    assert isinstance(name, unicode)
    if re.match(u'^[a-zA-Z][-a-zA-Z0-9]{0,199}$', name) is None:
        raise CheckError(u"Interner Name nicht wohlgeformt!",
                         u"Der Name darf lediglich Klein-, Großbuchstaben, Ziffern sowie Bindestriche enthalten, muss mit einem Buchstaben beginnen und darf nicht mehr als 200 Zeichen enthalten.")

def validateNonExistence(path, name):
    """
    check whether a name is already in use as internal representation, if so
    raise a CheckError. This also checks for additional rcs file extensions.

    @type name: bytes
    @type path: bytes
    @param name: name to check for existence
    @param path: base path in which to check for the name
    @raises CheckError:
    """
    assert isinstance(name, bytes)
    assert isinstance(path, bytes)
    if os.path.exists(os.path.join(path, name)) or \
           os.path.exists(os.path.join(path, name + b",v")):
        raise CheckError(u"Interner Name bereits vergeben!",
                         u"Wähle einen anderen Namen.")

def validateExistence(path, name):
    """
    check whether a name exsits. If not raise a CheckError.

    @type name: bytes
    @type path: bytes
    @param name: name to check for existence
    @param path: base path in which to check for the name
    @raises CheckError:
    """
    assert isinstance(name, bytes)
    assert isinstance(path, bytes)
    if not os.path.exists(os.path.join(path, name)):
        raise CheckError(u"Interner Name existiert nicht!",
                         u"Bitte den Namen korrigieren.")

def sanitizeBlobFilename(name):
    return u"einedatei.dat"

def validateUserConfig(config):
    """
    Try parsing the supplied config with ConfigParser. If this fails
    raise a CheckError saying so.

    @type config: unicode
    """
    assert isinstance(config, unicode)
    parser = ConfigParser()
    try:
        parser.readfp(io.StringIO(config))
    except configparser.ParsingError as err:
        raise CheckError(u"Es ist ein allgemeiner Parser-Fehler aufgetreten!",
                         u"Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)
    try:
        for name in parser.sections():
            for perm in parser.get(name, u'permissions').split(u','):
                if len(perm.strip().split(u' ')) != 2:
                    raise CheckError(
                        u"Fehler in Permissions.",
                        u"Das Recht '%s' für '%s' ist nicht wohlgeformt." %
                        (perm, name))
            parser.get(name, u'status')
            parser.get(name, u'password')
    except configparser.NoOptionError as err:
        raise CheckError(u"Es fehlt eine Angabe!",
                         u"Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)

def validateGroupConfig(config):
    """
    Try parsing the supplied config with ConfigParser. If this fails
    raise a CheckError saying so.

    @type config: unicode
    """
    assert isinstance(config, unicode)
    parser = ConfigParser()
    try:
        parser.readfp(io.StringIO(config))
    except configparser.Error as err:
        raise CheckError(u"Es ist ein allgemeiner Parser-Fehler aufgetreten!",
                         u"Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)
    try:
        for name in parser.sections():
            parser.get(name, u'title')
    except configparser.NoOptionError as err:
        raise CheckError(u"Es fehlt eine Angabe!",
                         u"Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)

class RcsUserInputError(CheckError):
    pass

def validateRcsRevision(versionnumber):
    """
    Check if versionnumber is a syntactically well-formed rcs version number

    @type versionnumber: bytes
    @raises RcsUserInputError:
    """
    assert isinstance(versionnumber, bytes)
    # Decoding with this encoding will not fail. Non-ascii bytes will be
    # rejected by the regex.
    versionnumber = versionnumber.decode("iso8859-1")
    if re.match(u'^[1-9][0-9]{0,10}\\.[1-9][0-9]{0,10}(\\.[1-9][0-9]{0,10}\\.[1-9][0-9]{0,10}){0,5}$',
                versionnumber) is None:
        raise RcsUserInputError(u"rcs version number syntactically malformed",
                                u"can only happen in hand-crafted requests")

class TarWriter:
    def __init__(self, gzip=False):
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

    def pushd(self, dirname):
        """Push a new directory on the directory stack. Further add* calls will
        place their files into this directory. The operation must be reverted
        using popd before close is called. The directory name must not contain
        a slash.
        @type dirname: bytes
        """
        assert isinstance(dirname, bytes)
        assert b"/" not in dirname
        if not isinstance(dirname, str):
            dirname = dirname.decode("iso8859-1")
        self.dirs.append(dirname)

    def popd(self):
        """Pop the topmost directory off the directory stack.
        @rtype: str
        @returns: the basename popped
        """
        assert self.dirs
        return self.dirs.pop()

    def read(self):
        data = self.io.getvalue()
        self.io.seek(0)
        self.io.truncate(0)
        return data

    def addChunk(self, name, content, lastchanged):
        """
        Add a file with given content and return some tar content generated
        along the way.

        @type name: bytes
        @type content: bytes
        @rtype: bytes
        @lastchanged: datetime
        """
        assert isinstance(name, bytes)
        assert isinstance(content, bytes)
        if not isinstance(name, str):
            name = name.decode("iso8859-1")
        assert isinstance(lastchanged, datetime.datetime)

        info = tarfile.TarInfo(self.prefix + name)
        info.size = len(content)
        info.mtime = calendar.timegm(lastchanged.utctimetuple())
        self.tar.addfile(info, io.BytesIO(content))
        return self.read()

    def addFileChunk(self, name, filename):
        """
        Add a regular file with given (tar) name and given (filesystem)
        filename and return some tar content generated along the way.
        @type name: bytes
        @type filename: bytes
        @rtype: bytes
        """
        if not isinstance(name, str):
            name = name.decode("iso8859-1")
        info = tarfile.TarInfo(self.prefix + name)
        with open(filename, "rb") as infile:
            infile.seek(0, 2)
            info.size = infile.tell()
            info.mtime = os.path.getmtime(filename)
            infile.seek(0)
            self.tar.addfile(info, infile)
        return self.read()

    def addDirChunk(self, name, dirname, excludes=[]):
        """
        Recursively add a filesystem directory dirname using the given name.
        Only regular files and directories are considered. Any basename that
        is contained in excludes is left out. The tar content generated along
        the way is returned as a bytes iterator.
        @type name: bytes
        @type dirname: bytes
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

    def close(self):
        """
        Close the TarWriter and return the remaining content.
        @rtype: bytes
        """
        assert not self.dirs
        self.tar.close()
        return self.io.getvalue()

def findlastchange(changes):
    """
    Given a list of rcs revision informations find the newest change.

    @param changes: list of dictionary containing the keys 'author',
                    'revision' and 'date'
    @type changes: [{str:object}]
    @rtype: {str:object}
    @returns: returns the dictionary with the latest date
    """
    return max(changes + [{'author': u'unkown', 'revision' : u'?',
                           'date' : epoch}], key=lambda x: x["date"])
