# -*- coding: utf-8 -*-

# todo:
# dates (7.\, August 2010 und 7.\,8.\,2010, 427--347~v.\,Chr.)
# ellipses (Wort~\ldots{})
# quotes ("`Danke, Dirk."' und das war's)
# acronyms
# units (40\,g, 50\,m)
# number specials (20\,\%, 19.\,Jahrhundert, 3.\,Person)
# escape percent
# improve dash handling (for errors like 3-9 and a-f)

from dokuforge.baseformatter import BaseFormatter
from dokuforge.parser import ParseLeaf

whitelist = ["pi"]

abbreviations = [["z", "B"], ["vgl"]]

units = ["m", "s", "V"]

class Context:
    def __init__(self, leaf, neighbours, environ):
        self.leaf = leaf
        self.neighbours = neighbours
        self.environ = environ
        self.index = neighbours.index(leaf)


    def inenviron(self, query):
        for x in query:
            if x in self.environ:
                return True
        return False


    def lookleafdata(self, n=1):
        try:
            if not isinstance(self.neighbours[self.index+n], ParseLeaf):
                return None
            return self.neighbours[self.index+n].data
        except IndexError:
            return None

    def lookleaftype(self, n=1):
        try:
            if not isinstance(self.neighbours[self.index+n], ParseLeaf):
                return None
            return self.neighbours[self.index+n].ident
        except IndexError:
            return None

    def comparedata(self, data):
        for i in range(len(data)):
            if not self.lookleafdata(i+1) == data[i]:
                return False
        return True

    def checkabbrev(self, abbrev):
        pos = 0
        for x in abbrev:
            if not self.lookleafdata(pos) == x and \
                self.lookleafdata(pos + 1) == u'.':
                return False
            pos += 2
            if self.lookleaftype(pos) == "Whitespace":
                pos += 1
        return True

    def countabbrev(self, abbrev):
        pos = 0
        for x in abbrev:
            if not self.lookleafdata(pos) == x and \
                self.lookleafdata(pos + 1) == u'.':
                return 0
            pos += 2
            if self.lookleaftype(pos) == "Whitespace":
                pos += 1
        return pos

    def scanfordash(self, pos=3):
        if self.lookleafdata(pos) == u'.' or \
            self.lookleafdata(pos + 1) == u'.' or \
            self.lookleafdata(pos + 2) == u'.':
            return False
        while not self.lookleafdata(pos + 2) == u'.':
            if self.lookleaftype(pos) == "Whitespace" and \
                self.lookleafdata(pos + 1) == u'-' and \
                self.lookleafdata(pos + 2) == u'-':
                return True
            pos += 1
        return False

    def checkunit(self, pos=1):
        return self.lookleafdata(pos) in units


class TeXFormatter(BaseFormatter):
    """
    Formatter for converting the tree representation into TeX for export.
    """
    ## escaping is done by the advanced_handle_* routines

    handle_heading = u"\\section{%s}".__mod__
    handle_subheading = u"\\subsection{%s}".__mod__
    handle_ednote = u"\\begin{ednote}%s\\end{ednote}".__mod__
    handle_displaymath = u"\\[%s\\]".__mod__
    handle_authors = u"\\authors{%s}".__mod__
    handle_paragraph = "%s".__mod__
    handle_emphasis = u"\\emph{%s}".__mod__
    handle_keyword = u"\\textbf{%s}".__mod__
    # inherit handle_inlinemath
    handle_list = u"\\begin{itemize}\n%s\n\end{itemize}".__mod__
    handle_item = u"\\item %s".__mod__
    handle_Dollar = u"%.0\\$%".__mod__


    def __init__(self, tree):
        BaseFormatter.__init__(self, tree)
        self.dashesseen = 0

    def handle_nestedednote(self, data):
        """
        Do not allow '{ednote}' inside ednotes to prevent '\end{ednote}'.
        """
        if data == u"ednote":
            return u"{\\@forbidden ednote}"
        else:
            return "{%s}" % data

    def advanced_handle_Backslash(self, leaf, context):
        if context.inenviron(["inlinemath", "displaymath"]) and \
            context.lookleafdata() in whitelist:
            return (u'\\' + context.lookleafdata(), 1)
        elif context.inenviron(["inlinemath", "displaymath"]) and \
            context.lookleaftype() == "Backslash":
            if context.lookleaftype(2) == "Newline":
                return (u'\\\\', 1)
            else:
                return (u'\\\\\n', 1)
        else:
            if context.lookleaftype() == "Backslash":
                return (u'\\@\\forbidden\\newline ', 1)
            elif context.lookleaftype() == "Word":
                return (u'\\@\\forbidden\\', 0)
            else:
                return (u'\\@\\forbidden\\ ', 0)

    def advanced_handle_Word(self, leaf, context):
        if context.lookleafdata() == u'.' and \
            not context.inenviron(["inlinemath", "displaymath"]):
            for abbrev in abbreviations:
                if context.checkabbrev(abbrev):
                    return(u'\\@' + u'.\\,'.join(abbrev) + u'.',
                           context.countabbrev(abbrev))
            return (leaf.data, 0)
        else:
            return (leaf.data, 0)

    def advanced_handle_Token(self, leaf, context):
        if context.inenviron(["ednote", "nestedednote"]):
            return (leaf.data, 0)
        elif leaf.data == u'.':
            if context.comparedata([u'.', u'.']):
                return (u'\\@\\ldots{}', 2)
            else:
                ## reset number of seen dashes at every full stop
                self.dashesseen = 0
                return (u'.', 0)
        elif leaf.data == u'-':
            if context.lookleafdata() == u'-':
                if not context.lookleaftype(2) == "Number":
                    if context.lookleaftype(2) == "Whitespace":
                        self.dashesseen += 1
                        ## == 0 since we allready increased dashesseen
                        if self.dashesseen % 2 == 0:
                            return (u'\\@--~', 2)
                        else:
                            return (u'\\@~--', 2)
                    else:
                        return (u'\\@--', 1)
                else:
                    return (u'--', 1)
            else:
                return (u'-', 0)
        elif leaf.data == u'%':
            return (u'\\%', 0)
        elif leaf.data == u'^':
            ## prevent '^^'
            skips = 0
            while context.lookleafdata(skips+1) == u'^':
                skips += 1
            return (u'^', skips)
        else:
            return (leaf.data, 0)

    def advanced_handle_Number(self, leaf, context):
        number = u''
        if len(leaf.data) < 5:
            number = leaf.data
        else:
            rem = len(leaf.data) % 3
            if rem > 0:
                number = leaf.data[0:rem] + u'\\,'
            pos = 0
            while 3*(pos+1) + rem <= len(leaf.data):
                number += leaf.data[3*pos+rem:3*(pos+1)+rem] + u'\\,'
                pos +=1
            number = number[:-2]
        skip = 0
        if context.lookleaftype() == "Whitespace":
            skip = 1
        if context.checkunit(1+skip):
            return (number + u'\\,' + context.lookleafdata(skip+1), skip+1)
        if context.lookleafdata(1+skip) == u'%':
            return (number + u'\\,\\%', skip+1)
        return (number, 0)

    def advanced_handle_Whitespace(self, leaf, context):
        if context.comparedata([u'-', u'-']):
            if self.dashesseen % 2 == 1 or not context.scanfordash():
                self.dashesseen += 1
                return (u'\\@~--', 2)
            else:
                return (u' ', 0)
        elif context.comparedata([u'.', u'.', u'.']):
            return (u'\\@~\\ldots{}', 3)
        else:
            return (u' ', 0)


    def generateoutput(self):
        """
        Take self.tree and generate an output string.

        This method adds all the bells and whistles the exporter has. It
        mainly calls supergenerateoutput. There do not have to be many
        specials here, since the root ParseTree may only contain paragraph,
        heading, subheading, authors, displaymath, list, ednote, Newline and
        Newpar.
        """
        output = u""
        for x in self.tree.tree:
            assert x.ident in ("paragraph", "heading", "subheading", "authors",
                               "displaymath", "list", "ednote", "Newpar",
                               "Newline")
            value, _ = self.advancedgenerateoutput(x, Context(x, self.tree.tree,
                                                              ["root"]))
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        return output

    def advancedgenerateoutput(self, tree, context):
        if isinstance(tree, ParseLeaf):
            data = tree.data
            skips = 0
            handler = None
            ## first try advanced handler
            try:
                handler = getattr(self, "advanced_handle_%s" % tree.ident)
            except AttributeError:
                pass
            else:
                data, skips = handler(tree, context)
            if handler is None:
                ## if no advanced handler, try normal handler
                try:
                    handler = getattr(self, "handle_%s" % tree.ident)
                except AttributeError:
                    pass
                else:
                    data = handler(data)
            return (data, skips)
        ## now we have a ParseTree
        output = u""
        skips = 0
        context.environ.append(tree.ident)
        for x in tree.tree:
            ## skip nodes, allready processed earlier in the loop
            if skips > 0:
                skips -= 1
                continue
            value, skips = self.advancedgenerateoutput(x, Context(x, tree.tree,
                                                                  context.environ))
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        context.environ.pop()
        return (output, 0)
