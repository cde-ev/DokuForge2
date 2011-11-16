#!/usr/bin/env python

from pyparsing import Dict, Group, OneOrMore, Optional, QuotedString, \
        Suppress, White, Word, ZeroOrMore, alphanums, alphas
import sys

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

result = rcsfile.parseFile(sys.argv[1])
print result.versions[result.header["head"]]["text"]
