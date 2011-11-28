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
    escapemap = {
            ord(u'\\'): u"\\forbidden\\"}

    escapeexceptions = ["ednote", "nestedednote"]

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

    def advanced_handle_Backslash(self, leaf, neighbours, context, escape):
        if not escape:
            if incontext(context, "ednote"):
                return (u'\\', 0, escape)
        if incontext(context, "inlinemath") or \
            incontext(context, "displaymath"):
            if lookleafdata(leaf, neighbours) in whitelist:
                return (u'\\' + lookleafdata(leaf, neighbours), 1, False)
            else:
                return (u'\\forbidden\\', 0, False)
        else:
            return (u'\\forbidden\\', 0, False)

    def generateoutput(self):
        """
        Take self.tree and generate an output string.

        This method adds all the bells and whistles the exporter has. It
        mainly calls supergenerateoutput. There do not have to be many
        specials here, since the root ParseTree may only contain paragraph,
        heading, subheading, authors, displaymath, list, ednote and Newpar.
        """
        output = u""
        for x in self.tree.tree:
            value, _ = self.advancedgenerateoutput(x, self.tree, ["root"])
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        return output

    def advancedgenerateoutput(self, tree, neighbours, context, escape = True):
        if isinstance(tree, ParseLeaf):
            data = tree.data
            skips = 0
            handler = None
            try:
                handler = getattr(self, "advanced_handle_%s" % tree.ident)
            except AttributeError:
                pass
            else:
                data, skips, escape = handler(tree, neighbours, context, escape)
            if handler is None:
                try:
                    handler = getattr(self, "handle_%s" % tree.ident)
                except AttributeError:
                    pass
                else:
                    data = handler(data)
            if escape:
                return (data.translate(self.escapemap), skips)
            return (data, skips)
        if tree.ident in self.escapeexceptions:
            escape=False
        output = u""
        context.append(tree.ident)
        skips = 0
        for x in tree.tree:
            if skips > 0:
                skips -= 1
                continue
            value, skips = self.advancedgenerateoutput(x, tree.tree, context, escape)
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        context.pop()
        return (output, 0)
