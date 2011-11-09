# -*- coding: utf-8 -*-

from dokuforge.baseparser import BaseParser

class DokuforgeToHtmlParser(BaseParser):
    """
    Parser for converting Dokuforge Syntax into viewable html.

    It works by scanning the text one token at a time (with a bit of
    lookahead) and remembering all context in a stack, so the meaning of
    tokens change as the context changes.

    @ivar debug: toggles debug output
    """
    escapemap = {
            '<': "&lt;",
            '>': "&gt;",
            '&': "&amp;",
            '"': "&#34;",
            "'": "&#39;"
        }

    def __init__(self, string, debug = False):
        BaseParser.__init__(self, string)
        self.debug = debug

    handle_heading = "<h3>%s</h3>".__mod__
    handle_subheading = "<h4>%s</h4>".__mod__
    handle_emphasis = "<i>%s</i>".__mod__
    handle_paragraph = "<p>%s</p>".__mod__
    handle_authors = handle_emphasis
    handle_keyword = "<b>%s</b>".__mod__
    handle_inlinemath = "$%s$".__mod__
    handle_displaymath = "$$%s$$".__mod__
    handle_ednote = "<pre>%s</pre>".__mod__
    handle_list = "<ul>\n%s</ul>".__mod__
    handle_item = "<li>%s</li>\n".__mod__
