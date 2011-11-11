# -*- coding: utf-8 -*-

from dokuforge.baseparser import BaseParser

class DokuforgeToTeXParser(BaseParser):
    """
    Parser for converting Dokuforge Syntax into TeX for export.

    It works by scanning the text one token at a time (with a bit of
    lookahead) and remembering all context in a stack, so the meaning of
    tokens change as the context changes.
    """
    escapemap = {
            ord(u'\\'): u"\\forbidden\\"}

    handle_ednote = lambda self, data: self.do_block(data, u"\\begin{ednote}%s\end{ednote}")
    handle_displaymath = lambda self, data: self.do_block(data, u"\\[%s\\]")
    handle_heading = lambda self, data: self.do_block(data, u"\\section{%s}")
    handle_subheading = lambda self, data: self.do_block(data, u"\\subsection{%s}")
    handle_authors = lambda self, data: self.do_block(data, u"\\authors{%s}")
    handle_paragraph = "%s".__mod__
    handle_emphasis = u"\\emph{%s}".__mod__
    handle_keyword = u"\\textbf{%s}".__mod__
    handle_inlinemath = u"$%s$".__mod__
    handle_list = u"\\begin{itemize}\n%s\n\end{itemize}".__mod__
    handle_item = u"\\item %s".__mod__

