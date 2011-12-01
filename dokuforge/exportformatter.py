# -*- coding: utf-8 -*-

from dokuforge.baseformatter import BaseFormatter

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
    handle_Dollar = u"%.0s\\$".__mod__
