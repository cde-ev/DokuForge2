# -*- coding: utf-8 -*-

import random
import subprocess
import re

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

def validateGroups(groupstring, allgroups):
    """
    check whether groupstring contains a valid set of groups. This means
    it may not be empty and it may not contain non-existent groups. If a
    check fails a CheckError is raised.

    @type groupstring: unicode
    @param groupstring: contains groups seperated by whitespace
    """
    assert isinstance(groupstring, unicode)
    groups = groupstring.split()
    if len(groups) == 0:
        raise CheckError(u"Keine Gruppen gefunden!",
                         u"Jede Akademie muss mindestens einer Gruppe angeh&ouml;ren. Bitte korrigieren und erneut versuchen.")
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
    """
    assert isinstance(title, unicode)
    if title == u"":
        raise CheckError(u"Leerer Titel!",
                         u"Der Titel darf nicht leer sein.")

def validateBlobLabel(label):
    """
    check whether a label for a blob is valid. This means matching a certain
    regexp. Otherwise raise a CheckError.

    @type label: unicode
    @param label: label to check
    """
    assert isinstance(label, unicode)
    if re.match('^[a-z0-9]{1,200}$', label) is None:
        raise CheckError(u"Kürzel nicht wohlgeformt!",
                         u"Das Kürzel darf lediglich Kleinbuchstaben und Ziffern enthalten und auch nicht leer sein.")

