# -*- coding: utf-8 -*-

import random
import subprocess
import re
import os
import ConfigParser
from cStringIO import StringIO

try:
    check_output = subprocess.check_output
except AttributeError:
    def check_output(cmdline):
        proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
        output, _ = proc.communicate()
        if proc.returncode:
            raise subprocess.CalledProcessError()
        return output


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
    @type s: str
    @rtype: bool
    """
    if s == "True" or s == "true" or s == "t":
        return True
    return False

class CheckError(StandardError):
    def __init__(self, msg, exp):
        StandardError.__init__(self, msg)
        assert isinstance(msg, unicode)
        assert isinstance(exp, unicode)
        self.message = msg
        self.explanation = exp
    def __str__(self):
        return self.message

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
    if re.match('^[ \t]*$', title) is not None:
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
    if re.match('^[a-z0-9]{1,200}$', label) is None:
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

    @type filename: str
    @param filename: filename to check
    @raises InvalidBlobFilename:
    """
    assert isinstance(filename, str)
    if re.match('^[a-zA-Z0-9][-a-zA-Z0-9_.]{1,200}[a-zA-Z0-9]$', filename) is None:
        raise InvalidBlobFilename(u"Dateiname nicht wohlgeformt!",
                                  u"Bitte alle Sonderzeichen aus dem Dateinamen entfernen und erneut versuchen. Der Dateinahme darf nicht mehr als 200 Zeichen enthalten.")

def validateInternalName(name):
    """
    check whether a name is accepted for representing something on disk, i.e.
    for the internal representation. This means matching a certain
    regexp. Otherwise raise a CheckError.

    @type name: str
    @param name: name to check
    @raises CheckError:
    """
    assert isinstance(name, str)
    if re.match('^[a-zA-Z][-a-zA-Z0-9]{0,199}$', name) is None:
        raise CheckError(u"Interner Name nicht wohlgeformt!",
                         u"Der Name darf lediglich Klein-, Großbuchstaben, Ziffern sowie Bindestriche enthalten, muss mit einem Buchstaben beginnen und darf nicht mehr als 200 Zeichen enthalten.")

def validateNonExistence(path, name):
    """
    check whether a name is already in use as internal representation, if so
    raise a CheckError. This also checks for additional rcs file extensions.

    @type name: str
    @type path: str
    @param name: name to check for existence
    @param path: base path in which to check for the name
    @raises CheckError:
    """
    assert isinstance(name, str)
    assert isinstance(path, str)
    if os.path.exists(os.path.join(path, name)) or \
           os.path.exists(os.path.join(path, name + ",v")):
        raise CheckError(u"Interner Name bereits vergeben!",
                         u"Wähle einen anderen Namen.")

def validateExistence(path, name):
    """
    check whether a name exsits. If not raise a CheckError.

    @type name: str
    @type path: str
    @param name: name to check for existence
    @param path: base path in which to check for the name
    @raises CheckError:
    """
    assert isinstance(name, str)
    assert isinstance(path, str)
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
    parser = ConfigParser.SafeConfigParser()
    try:
        parser.readfp(StringIO(config.encode("utf8")))
    except ConfigParser.ParsingError as err:
        raise CheckError(u"Es ist ein allgemeiner Parser-Fehler aufgetreten!",
                         u"Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)
    try:
        for name in parser.sections():
            parser.get(name, 'permissions')
            parser.get(name, 'status')
            parser.get(name, 'password')
    except ConfigParser.NoOptionError as err:
        raise CheckError(u"Es fehlt eine Angabe!",
                         u"Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)

def validateGroupConfig(config):
    """
    Try parsing the supplied config with ConfigParser. If this fails
    raise a CheckError saying so.

    @type config: unicode
    """
    assert isinstance(config, unicode)
    parser = ConfigParser.SafeConfigParser()
    try:
        parser.readfp(StringIO(config.encode("utf8")))
    except ConfigParser.ParsingError as err:
        raise CheckError(u"Es ist ein allgemeiner Parser-Fehler aufgetreten!",
                         u"Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)
    try:
        for name in parser.sections():
            parser.get(name, 'title')
    except ConfigParser.NoOptionError as err:
        raise CheckError(u"Es fehlt eine Angabe!",
                         u"Der Fehler lautetete: %s. Bitte korrigiere ihn und speichere erneut." % err.message)
