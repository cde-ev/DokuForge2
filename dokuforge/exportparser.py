# -*- coding: utf-8 -*-

from dokuforge.baseparser import BaseParser
from dokuforge.common import end_with_newpar

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

    def handle_paragraph(self, data):
        self.ensurenewpar()
        return end_with_newpar(data)

    handle_heading = lambda self, data: self.do_block(data, "\\section{%s}")
    handle_subheading = lambda self, data: self.do_block(data, "\\subsection{%s}")
    handle_authors = lambda self, data: self.do_block(data, "\\authors{%s}")
    handle_emphasis = "\\emph{%s}".__mod__
    handle_keyword = "\\textbf{%s}".__mod__
    handle_inlinemath = "$%s$".__mod__
    handle_displaymath = lambda self, data: self.do_block(data, "\\[%s\\]")
    handle_ednote = lambda self, data: self.do_block(data, "\\begin{ednote}%s\end{ednote}")
    handle_list = lambda self, data: self.do_environ(data, "\\begin{itemize}\n%s\end{itemize}")
    handle_item = lambda self, data: self.do_block(data, "\\item %s")

    def postprocessor(self, data):
        ## compress excessive newlines
        while '\n\n\n' in data:
            data = data.replace('\n\n\n', '\n\n')
        return data
