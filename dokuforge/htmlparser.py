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

    handle_ednote = lambda self, data: self.do_block(data, u"<pre>%s</pre>")
    handle_paragraph = lambda self, data: self.do_block(data, u"<p>%s</p>")
    handle_list = lambda self, data: self.do_environ(data, u"<ul>%s</ul>")
    handle_item = lambda self, data: self.do_block(data, u"<li>%s</li>")
    handle_displaymath = lambda self, data: self.do_block(data, u"$$%s$$")
    handle_authors = lambda self, data: self.do_block(data, u"<i>%s</i>")
    handle_heading = lambda self, data: self.do_block(data, u"<h3>%s</h3>")
    handle_subheading = lambda self, data: self.do_block(data, u"<h4>%s</h4>")
    handle_emphasis = u"<i>%s</i>".__mod__
    handle_keyword = u"<b>%s</b>".__mod__
    handle_inlinemath = u"$%s$".__mod__
