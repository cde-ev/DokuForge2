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

    handle_ednote = lambda self, data: self.do_block(data, "<pre>%s</pre>")
    handle_paragraph = lambda self, data: self.do_block(data, "<p>%s</p>")
    handle_list = lambda self, data: self.do_environ(data, "<ul>%s</ul>")
    handle_item = lambda self, data: self.do_block(data, "<li>%s</li>")
    handle_displaymath = lambda self, data: self.do_block(data, "$$%s$$")
    handle_authors = lambda self, data: self.do_block(data, "<i>%s</i>")
    handle_heading = lambda self, data: self.do_block(data, "<h3>%s</h3>")
    handle_subheading = lambda self, data: self.do_block(data, "<h4>%s</h4>")
    handle_emphasis = "<i>%s</i>".__mod__
    handle_keyword = "<b>%s</b>".__mod__
    handle_inlinemath = "$%s$".__mod__
