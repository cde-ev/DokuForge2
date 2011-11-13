# -*- coding: utf-8 -*-

from dokuforge.baseparser import BaseParser

class DokuforgeToHtmlParser(BaseParser):
    """
    Parser for converting Dokuforge Syntax into viewable html.

    It works by scanning the text one token at a time (with a bit of
    lookahead) and remembering all context in a stack, so the meaning of
    tokens change as the context changes.
    """
    escapemap = {
            ord(u'<'): u"&lt;",
            ord(u'>'): u"&gt;",
            ord(u'&'): u"&amp;",
            ord(u'"'): u"&#34;",
            ord(u"'"): u"&#39;"
        }

    def handle_heading(self, data):
        if self.lookprintabletoken() == u'(':
            ## activate paren
            self.pushstate("authorsnext")
        self.pushstate("wantsnewline")
        return u"<h3>%s</h3>" % data

    def handle_subheading(self, data):
        if self.lookprintabletoken() == u'(':
            ## activate paren
            self.pushstate("authorsnext")
        self.pushstate("wantsnewline")
        return u"<h4>%s</h4>" % data

    handle_ednote = lambda self, data: self.do_block(data, u"<pre>%s</pre>")
    handle_displaymath = lambda self, data: self.do_block(data, u"$$%s$$")
    handle_authors = lambda self, data: self.do_block(data, u"<i>%s</i>")
    handle_paragraph = "<p>%s</p>".__mod__
    handle_list = u"<ul>\n%s\n</ul>".__mod__
    handle_item = u"<li>%s</li>".__mod__
    handle_emphasis = u"<i>%s</i>".__mod__
    handle_keyword = u"<b>%s</b>".__mod__
    # inherit handle_inlinemath
