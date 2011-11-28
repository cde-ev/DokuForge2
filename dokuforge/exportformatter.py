# -*- coding: utf-8 -*-

from dokuforge.baseformatter import BaseFormatter
from dokuforge.parser import ParseLeaf

def incontext(context, query):
    return query in context

whitelist = ["pi"]

def lookleafdata(leaf, neighbours):
    index = neighbours.index(leaf)
    try:
        if not isinstance(neighbours[index+1], ParseLeaf):
            return None
        return neighbours[index+1].data
    except IndexError:
        return None

class TeXFormatter(BaseFormatter):
    """
    Formatter for converting the tree representation into TeX for export.
    """
    ## escaping is done by the advanced_hendle_* routines

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

    def advanced_handle_Backslash(self, leaf, neighbours, context):
        if incontext(context, "ednote"):
            return (u'\\', 0)
        if incontext(context, "inlinemath") or \
            incontext(context, "displaymath"):
            if lookleafdata(leaf, neighbours) in whitelist:
                return (u'\\' + lookleafdata(leaf, neighbours), 1)
            else:
                return (u'\\forbidden\\', 0)
        else:
            return (u'\\forbidden\\', 0)

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
