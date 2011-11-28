# -*- coding: utf-8 -*-

from dokuforge.baseformatter import BaseFormatter
from dokuforge.parser import ParseLeaf

def incontext(context, query):
    return query in context

whitelist = ["pi"]

def lookleafdata(leaf, neighbours, n=1):
    index = neighbours.index(leaf)
    try:
        if not isinstance(neighbours[index+n], ParseLeaf):
            return None
        return neighbours[index+n].data
    except IndexError:
        return None

def lookleaftype(leaf, neighbours, n=1):
    index = neighbours.index(leaf)
    try:
        if not isinstance(neighbours[index+n], ParseLeaf):
            return None
        return neighbours[index+n].ident
    except IndexError:
        return None

def comparedata(leaf, neighbours, data):
    for i in len(data):
        if not lookleafdata(leaf, neighbours, i+1) == data[i]:
            return False
    return True

class TeXFormatter(BaseFormatter):
    """
    Formatter for converting the tree representation into TeX for export.
    """
    ## escaping is done by the advanced_handle_* routines

    handle_heading = u"\\section{%s}".__mod__
    handle_subheading = u"\\subsection{%s}".__mod__
    handle_ednote = u"\\begin{ednote}%s\end{ednote}".__mod__
    handle_displaymath = u"\\[%s\\]".__mod__
    handle_authors = u"\\authors{%s}".__mod__
    handle_paragraph = "%s".__mod__
    handle_emphasis = u"\\emph{%s}".__mod__
    handle_keyword = u"\\textbf{%s}".__mod__
    # inherit handle_inlinemath
    handle_list = u"\\begin{itemize}\n%s\n\end{itemize}".__mod__
    handle_item = u"\\item %s".__mod__
    handle_Dollar = u"%.0\\$%".__mod__

    def handle_nestedednote(self, data):
        """
        Do not allow '{ednote}' inside ednotes to prevent '\end{ednote}'.
        """
        if data == u"ednote":
            return u"{\\@forbidden ednote}"
        else:
            return "{%s}" % data

    def advanced_handle_Backslash(self, leaf, neighbours, context):
        if incontext(context, "ednote"):
            return (u'\\', 0)
        elif ( incontext(context, "inlinemath") or \
               incontext(context, "displaymath")) and \
            lookleafdata(leaf, neighbours) in whitelist:
            return (u'\\' + lookleafdata(leaf, neighbours), 1)
        elif ( incontext(context, "inlinemath") or \
               incontext(context, "displaymath")) and \
            lookleaftype(leaf, neighbours) == "Backslash":
            if lookleaftype(leaf, neighbours, 2) == "Newline":
                return (u'\\\\', 1)
            else:
                return (u'\\\\\n', 1)
        else:
            if lookleaftype(leaf, neighbours) == "Backslash":
                return (u'\\@\\forbidden\\newline ', 1)
            else:
                return (u'\\@\\forbidden\\', 0)

    def advanced_handle_Token(self, leaf, neighbours, context):
        if leaf.data == u'^':
            ## prevent '^^'
            skips = 0
            while lookleafdata(leaf, neighbours, skips+1) == u'^':
                skips += 1
            return (u'^', skips)
        else:
            return (leaf.data, 0)


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
            value, _ = self.advancedgenerateoutput(x, self.tree, ["root"])
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        return output

    def advancedgenerateoutput(self, tree, neighbours, context):
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
                data, skips = handler(tree, neighbours, context)
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
        context.append(tree.ident)
        skips = 0
        for x in tree.tree:
            ## skip nodes, allready processed earlier in the loop
            if skips > 0:
                skips -= 1
                continue
            value, skips = self.advancedgenerateoutput(x, tree.tree, context)
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        context.pop()
        return (output, 0)
