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

    handle_heading = u"<h3>%s</h3>".__mod__
    handle_subheading = u"<h4>%s</h4>".__mod__
    handle_ednote = u"<pre>%s</pre>".__mod__
    handle_displaymath = u"$$%s$$".__mod__
    handle_authors = u"<i>%s</i>".__mod__
    handle_paragraph = "<p>%s</p>".__mod__
    handle_list = u"<ul>\n%s\n</ul>".__mod__
    handle_item = u"<li>%s</li>".__mod__
    handle_emphasis = u"<i>%s</i>".__mod__
    handle_keyword = u"<b>%s</b>".__mod__
    # inherit handle_inlinemath
