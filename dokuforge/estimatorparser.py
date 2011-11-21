#!/usr/bin/env python

from dokuforge.baseparser import BaseParser

class Estimate:
    """An estimate in chars. Estimates can be added and automatically coerce
    strings and ints."""
    def __init__(self, value):
        """
        @type value: Estimate or unicode or str or int
        """
        if isinstance(value, Estimate):
            value = value.value
        elif isinstance(value, unicode) or isinstance(value, str):
            value = len(value)
        assert isinstance(value, int)
        self.value = value

    def __add__(self, other):
        if isinstance(other, Estimate):
            return Estimate(self.value + other.value)
        return self + Estimate(other)

    __radd__ = __add__

    def __int__(self):
        return self.value

    def __repr__(self):
        return "%s(%d)" % (self.__class__.__name__, self.value)

class Estimator(BaseParser):
    """The estimator parser computes an estimate of the length of the document
    in bytes. It thinks of a page of as lines filled with monospace characters.
    So certain structures which are known to cause a linebreak account at least
    a full line. The result of this parser is an int.
    """
    ## this is an empirical number, may be tuned later
    linelength = 85

    def __init__(self, string, raw=False, ednotes=False):
        """
        @param string: string to parse
        @param raw: toggles counting of single chars vs. sophisticated
          accounting for full lines, default is the sophisticated method
        @param ednots: toggles counting of ednotes, default is not to count
          them
        @type string: unicode
        @type raw: bool
        @type ednote: bool
        """
        BaseParser.__init__(self, string)
        self.ednotes = ednotes
        self.raw = raw

    def nlines(self, line, n):
        """Return an estimate for the length of this line.

        If raw is False this estimates the length to be at least n lines so
        content which stands on a line itself is correctly accounted for.
        @type line: unicode
        @type n: int
        @rtype: Estimate
        @returns: an estimate of the length of the line, but at least n lines
        """
        if not self.raw:
            return Estimate(max(len(line), n*self.linelength))
        else:
            return Estimate(line)

    handle_heading = lambda self, line: self.nlines(line, 2)
    handle_subheading = lambda self, line: self.nlines(line, 1)
    handle_authors = lambda self, line: self.nlines(line, 1)
    handle_item = lambda self, line: self.nlines(line, 1)
    handle_displaymath = lambda self, line: self.nlines(line, 3)

    def handle_ednote(self, ednote):
        """include ednotes according to self.ednotes"""
        if self.ednotes:
            return Estimate(ednote)
        else:
            return Estimate(0)

    def result(self):
        return int(Estimate(BaseParser.result(self)))