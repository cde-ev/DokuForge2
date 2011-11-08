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
            '"': "&#34;"}
    
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

    def cleanup(self):
        """
        close all open states
        """
        while not self.lookstate() == "normal":
            currentstate = self.lookstate()
            if currentstate == "start":
                self.popstate()
                self.pushstate("normal")
            elif currentstate in ("authors", "displaymath", "heading",
                                  "keyword", "paragraph", "seennewline",
                                  "seennewpar", "subheading"):
                self.popstate()
                self.put('\n')
            elif currentstate in ("authorsnext", "headingnext", "listnext",
                                  "keywordnext"):
                self.popstate()
                self.put('\n\n')
            elif currentstate == "list":
                self.popstate()
                self.put('</li>\n</ul>\n')
            elif currentstate in ("emphasis", "inlinemath"):
                self.popstate()
            elif currentstate == "ednote":
                self.popstate()
                if not self.lookstate() == "ednote":
                    self.put('</pre>')
            elif currentstate == "seenwhitespace":
                self.popstate()
                self.put(' ')
            else:
                raise ValueError("invalid state")

    def predictnextstructure(self, token):
        """
        After a newline some future tokens have a special meaning. This
        function is to be called after every newline and marks these tokens
        as active.
        """
        if token == '[':
            self.pushstate("headingnext")
        if token == '-':
            self.pushstate("listnext")

    def parse(self):
        """
        The actual parser.
        """
        while True:
            ## retrieve token
            try:
                token = self.poptoken()
            except IndexError:
                self.cleanup()
                break
            ## retrieve current state
            currentstate = self.lookstate()
            ## print some nice stuff if in debug mode
            ## actually useful, I quite missed something like this in the
            ## big cannons I tried before
            if self.debug:
                print self
                try:
                    print "Token:", token
                except UnicodeEncodeError:
                    print "Token: <???> unicode token"
            ## process the token

            ## first handle ednotes
            ## here everything is copied verbatim
            if currentstate == "ednote":
                if token == '{':
                    self.pushstate("ednote")
                    self.put('{')
                elif token == '}':
                    self.popstate()
                    if self.lookstate() == "ednote":
                        self.put('}')
                    else:
                        self.put('</pre>\n')
                else:
                    self.putescaped(token)
                continue

            ## second handle whitespace
            ## we contract whitespace as far as sensible
            if token == ' ' or token == '\t':
                if currentstate not in ("start", "seenwhitespace",
                                        "seennewline","seennewpar"):
                    self.pushstate("seenwhitespace")
                continue
            elif token == '\n':
                if currentstate == "start" or currentstate == "seennewpar":
                    pass
                elif currentstate == "seenwhitespace":
                    self.popstate()
                    self.pushstate("seennewline")
                elif currentstate == "seennewline":
                    self.popstate()
                    self.pushstate("seennewpar")
                else:
                    self.pushstate("seennewline")
                continue

            ## now we have a non-whitespace token so we clean up the state
            ## i.e. remove whitespace from the context
            ## a double newline ends all environments (except ednotes)
            if currentstate == "paragraph":
                ## minor optimization, but I feel it is worth it
                ## to shortcircuit this selfment
                pass
            elif currentstate == "seenwhitespace":
                self.popstate()
                self.put(' ')
            elif currentstate == "seennewline":
                self.popstate()
                self.put('\n')
                ## activate special tokens
                self.predictnextstructure(token)
            elif currentstate == "seennewpar":
                self.popstate()
                self.cleanup()
                self.put('\n')
                ## activate special tokens
                self.predictnextstructure(token)
            elif currentstate == "start":
                self.popstate()
                self.pushstate("normal")
                ## activate special tokens
                self.predictnextstructure(token)

            ## third handle math
            ## this deactivates all other special characters
            ## even ednotes since math needs curly braces
            if self.lookstate() == "inlinemath" or \
                   self.lookstate() == "displaymath":
                ## math special token $
                if token == '$':
                    if currentstate == "inlinemath":
                        self.popstate()
                    else:
                        # displaymath
                        self.popstate()
                        if self.looktoken() == '$':
                            self.poptoken()
                ## but we still need to escape
                else:
                    self.putescaped(token)
                continue

            ## fourth if a new paragraph is beginning insert it into the context
            if self.lookstate() == "normal":
                self.pushstate("paragraph")
                if token == '*':
                    self.pushstate("keywordnext")

            ## update current state, since it could be modified
            currentstate = self.lookstate()

            ## fifth now we handle all printable tokens
            ### ednotes as { note to self }
            if token == '{':
                self.cleanup()
                self.pushstate("ednote")
                self.put('<pre>')
            ### math in the forms $inline$ and $$display$$
            elif token == '$':
                if self.looktoken() == '$':
                    self.poptoken()
                    self.pushstate("displaymath")
                else:
                    self.pushstate("inlinemath")
            ### [heading] and [[subheading]]
            ### with optional (authors) following
            elif token == '[':
                if currentstate == "headingnext":
                    self.popstate()
                    self.cleanup()
                    if self.looktoken() == '[':
                        self.poptoken()
                        self.pushstate("subheading")
                    else:
                        self.pushstate("heading")
                else:
                    self.put(token)
            elif token == ']':
                if currentstate == "heading":
                    self.popstate()
                    if self.lookprintabletoken() == '(':
                        self.pushstate("authorsnext")
                elif currentstate == "subheading":
                    if self.looktoken() == ']':
                        self.poptoken()
                        self.popstate()
                        if self.lookprintabletoken() == '(':
                            ## activate paren
                            self.pushstate("authorsnext")
                    else:
                        self.put(token)
                else:
                    self.put(token)
            ### (authors) only available after [heading] and [[subheading]]
            elif token == '(':
                if currentstate == "authorsnext":
                    self.popstate()
                    self.pushstate("authors")
                else:
                    self.put(token)
            elif token == ')':
                if currentstate == "authors":
                    self.popstate()
                else:
                    self.put(token)
            ### _emphasis_
            elif token == '_':
                if currentstate == "emphasis":
                    self.popstate()
                else:
                    self.pushstate("emphasis")
            ### *keywords* only avalailable at the beginnig of paragraphs
            elif token == '*':
                if currentstate == "keywordnext":
                    self.popstate()
                    self.pushstate("keyword")
                elif currentstate == "keyword":
                    self.popstate()
                else:
                    self.put(token)
            ### lists only available at the beginning of lines
            ### - items
            ### - like
            ### - this
            elif token == '-':
                if currentstate == "listnext":
                    self.popstate()
                    if self.lookstate() == "list":
                        self.put('</li>\n<li>')
                    else:
                        self.cleanup()
                        self.put('<ul>\n<li>')
                        self.pushstate("list")
                else:
                    self.put(token)
            ### the default case for all the non-special tokens
            ### but escaping the html special tokens
            else:
                self.putescaped(token)

        ## finally return the result
        return self.result()
