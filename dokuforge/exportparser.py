# -*- coding: utf-8 -*-

from dokuforge.baseparser import BaseParser

class DokuforgeToTeXParser(BaseParser):
    """
    Parser for converting Dokuforge Syntax into TeX for export.

    It works by scanning the text one token at a time (with a bit of
    lookahead) and remembering all context in a stack, so the meaning of
    tokens change as the context changes.

    @ivar debug: toggles debug output
    """
    escapemap = {
            '\\': "\\forbidden\\"}

    def __init__(self, string, debug = False):
        BaseParser.__init__(self, string)
        self.debug = debug

    handle_heading = "\\section{%s}".__mod__
    handle_subheading = "\\subsection{%s}".__mod__
    handle_emphasis = "\\emph{%s}".__mod__
    handle_paragraph = "%s\n\\par\n".__mod__
    handle_authors = "\\authors{%s}".__mod__
    handle_keyword = "\\textbf{%s}".__mod__
    handle_inlinemath = "$%s$".__mod__
    handle_displaymath = "\\[%s\\]".__mod__
    handle_ednote = "\\begin{ednote}%s\end{ednote}".__mod__
    handle_list = "\\begin{itemize}\n%s\end{itemize}".__mod__
    handle_item = "\\item %s\n".__mod__
