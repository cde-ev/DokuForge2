# -*- coding: utf-8 -*-

from dokuforge.baseformatter import BaseFormatter

class HtmlFormatter(BaseFormatter):
    """
    Formatter for converting the tree representation into viewable html.
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
    handle_ednote = u"<pre class=\"ednote\">%s</pre>".__mod__
    handle_authors = u"<i>%s</i>".__mod__
    handle_paragraph = "<p>%s</p>".__mod__
    handle_list = u"<ul>\n%s\n</ul>".__mod__
    handle_item = u"<li>%s</li>".__mod__
    handle_emphasis = u"<i>%s</i>".__mod__
    handle_keyword = u"<b>%s</b>".__mod__
    # inherit handle_inlinemath
    handle_displaymath = u"<div class=\"displaymath\">$$%1s$$</div>".__mod__
    handle_Dollar = u"%.0\\$%".__mod__
