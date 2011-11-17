#!/usr/bin/env python

from pyparsing import Dict, Group, OneOrMore, Optional, QuotedString, \
        Suppress, White, Word, ZeroOrMore, alphanums, alphas

semicolon = Suppress(";").leaveWhitespace()
attrname = Word(alphas)("attr").leaveWhitespace()
whitespace = White(" \t").suppress().leaveWhitespace()
newline = Suppress("\n").leaveWhitespace()
maybenl = (Optional(whitespace) + Optional(newline)).suppress()
doublenl = newline + newline
atstring = QuotedString("@", escQuote="@@", multiline=True)("value")
simpleval = Word(alphanums + ".")("value").leaveWhitespace()

attribute = Group(attrname + Optional(whitespace +
                                      Optional(atstring | simpleval)) +
                  semicolon + maybenl)

block = Dict(OneOrMore(attribute) + newline)

verblock = Group(simpleval + newline + block)

verblocks = Group(OneOrMore(verblock))

dataattr = Group(attrname + newline + atstring + newline)

version = Group(simpleval + newline + Dict(OneOrMore(dataattr)))

versions = Dict(version + ZeroOrMore(doublenl + version))

rcsfile = block("header") + newline + verblocks("verblocks") + newline + \
          dataattr("desc") + doublenl + versions("versions")

class RCS:
    def __init__(self, parseresult):
        """
        @type parseresult: pyparsing.ParseResult
        @param parseresult: a rcsfile parse result
        """
        self.parseresult = parseresult

    @classmethod
    def parse(cls, content):
        """
        @type content: str
        @param content: a rcs file
        @rtype: RCS
        """
        assert isinstance(content, str)
        return cls(rcsfile.parseString(content))

    def headrevision(self):
        """
        @rtype: str
        @raises KeyError:
        """
        return self.parseresult.header["head"]

    def headtext(self):
        """
        @rtype: str
        @raises KeyError:
        """
        return self.parseresult.versions[self.headrevision()]["text"]

if __name__ == '__main__':
    import sys
    result = rcsfile.parseFile(sys.argv[1])
    print RCS(result).headtext()
