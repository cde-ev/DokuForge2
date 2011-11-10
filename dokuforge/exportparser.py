# -*- coding: utf-8 -*-

from dokuforge.baseparser import BaseParser
from dokuforge.common import end_with_newpar

class DokuforgeToTeXParser(BaseParser):
    """
    Parser for converting Dokuforge Syntax into TeX for export.

    It works by scanning the text one token at a time (with a bit of
    lookahead) and remembering all context in a stack, so the meaning of
    tokens change as the context changes.
    """
    escapemap = {
            u'\\': u"\\forbidden\\"}

    def handle_paragraph(self, data):
        self.ensurenewpar()
        return end_with_newpar(data)

    handle_heading = lambda self, data: self.do_block(data, u"\\section{%s}")
    handle_subheading = lambda self, data: self.do_block(data, u"\\subsection{%s}")
    handle_authors = lambda self, data: self.do_block(data, u"\\authors{%s}")
    handle_emphasis = u"\\emph{%s}".__mod__
    handle_keyword = u"\\textbf{%s}".__mod__
    handle_inlinemath = u"$%s$".__mod__
    handle_displaymath = lambda self, data: self.do_block(data, u"\\[%s\\]")
    handle_ednote = lambda self, data: self.do_block(data, u"\\begin{ednote}%s\end{ednote}")
    handle_list = lambda self, data: self.do_environ(data, u"\\begin{itemize}\n%s\end{itemize}")
    handle_item = lambda self, data: self.do_block(data, u"\\item %s")

    def postprocessor(self, data):
        ## compress excessive newlines
        while u'\n\n\n' in data:
            data = data.replace(u'\n\n\n', u'\n\n')
        return data
