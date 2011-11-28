# -*- coding: utf-8 -*-

from dokuforge.baseformatter import BaseFormatter
from dokuforge.parser import ParseLeaf

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

    def generateoutput(self):
        """
        Take self.tree and generate an output string.

        This method adds all the bells and whistles the exporter has.

        This uses the handle_* methods to recursively transform the
        tree. The escaping is done with escapemap and controlled by
        escapeexceptions.
        """
        output = u""
        for x in self.tree.tree:
            value = self.supergenerateoutput(x, self.tree, ["root"])
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        return output

    def supergenerateoutput(self, tree, neighbours, context, escape = True):
        if isinstance(tree, ParseLeaf):
            data = tree.data
            try:
                handler = getattr(self, "handle_%s" % tree.ident)
            except AttributeError:
                pass
            else:
                data = handler(data)
            if escape:
                return data.translate(self.escapemap)
            return data
        if tree.ident in self.escapeexceptions:
            escape=False
        output = u""
        context.append(tree.ident)
        for x in tree.tree:
            value = self.supergenerateoutput(x, tree.tree, context, escape)
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        context.pop()
        return output
