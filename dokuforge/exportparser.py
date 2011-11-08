# -*- coding: utf-8 -*-

from dokuforge.baseparser import BaseParser

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

    def cleanup(self):
        """
        close all open states
        """
        while not self.lookstate() == "normal":
            currentstate = self.lookstate()
            if currentstate == "start":
                self.popstate()
                self.pushstate("normal")
            elif currentstate == "heading":
                self.popstate()
                self.put('}\n')
            elif currentstate == "subheading":
                self.popstate()
                self.put('}\n')
            elif currentstate == "authorsnext":
                self.popstate()
                self.put('\n\n')
            elif currentstate == "headingnext":
                self.popstate()
                self.put('\n\n')
            elif currentstate == "listnext":
                self.popstate()
                self.put('\n\n')
            elif currentstate == "authors":
                self.popstate()
                self.put('}\n')
            elif currentstate == "list":
                self.popstate()
                self.put('\n\end{itemize}\n')
            elif currentstate == "paragraph":
                self.popstate()
                self.put('\n\par\n')
            elif currentstate == "emphasis":
                self.popstate()
                self.put('}')
            elif currentstate == "keywordnext":
                self.popstate()
                self.put('\n\n')
            elif currentstate == "keyword":
                self.popstate()
                self.put('}\n')
            elif currentstate == "ednote":
                self.popstate()
                if not self.lookstate() == "ednote":
                    self.put('\end{ednote}')
            elif currentstate == "inlinemath":
                self.popstate()
                self.put('$')
            elif currentstate == "displaymath":
                self.popstate()
                self.put('\]\n')
            elif currentstate == "seenwhitespace":
                self.popstate()
                self.put(' ')
            elif currentstate == "seennewline":
                self.popstate()
                self.put('\n')
            elif currentstate == "seennewpar":
                self.popstate()
                self.put('\n\par\n')
            else:
                pass

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
                    self.put('\begin{ednote}')
                elif token == '}':
                    self.popstate()
                    if self.lookstate() == "ednote":
                        self.put('}')
                    else:
                        self.put('\end{ednote}\n')
                else:
                    # FIME regulate escaping
                    self.putescaped(token)
                continue

            ## second handle whitespace
            ## we contract whitespace as far as sensible
            if token == ' ' or token == '\t':
                if currentstate == "start" or \
                       currentstate == "seenwhitespace" or \
                       currentstate == "seennewline" or \
                       currentstate == "seennewpar":
                    pass
                else:
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
                        self.put(token)
                    else:
                        # displaymath
                        self.popstate()
                        if self.looktoken() == '$':
                            self.poptoken()
                            self.put(r'\]')
                        else:
                            self.put(r'\]')
                ## but we still need to escape
                else:
                    self.putescaped(token)
                continue

            ## fourth if a new paragraph is beginning insert it into the context
            if self.lookstate() == "normal":
                self.put('\n')
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
                self.put('\\begin{ednote}\n')
            ### math in the forms $inline$ and $$display$$
            elif token == '$':
                if self.looktoken() == '$':
                    self.poptoken()
                    self.pushstate("displaymath")
                    self.put(r'\[')
                else:
                    self.pushstate("inlinemath")
                    self.put(token)
            ### [heading] and [[subheading]]
            ### with optional (authors) following
            elif token == '[':
                if currentstate == "headingnext":
                    self.popstate()
                    self.cleanup()
                    if self.looktoken() == '[':
                        self.poptoken()
                        self.put(r'\subsection{')
                        self.pushstate("subheading")
                    else:
                        self.put(r'\section{')
                        self.pushstate("heading")
                else:
                    self.put(token)
            elif token == ']':
                if currentstate == "heading":
                    self.popstate()
                    self.put('}')
                    if self.lookprintabletoken() == '(':
                        self.pushstate("authorsnext")
                elif currentstate == "subheading":
                    if self.looktoken() == ']':
                        self.poptoken()
                        self.popstate()
                        self.put('}')
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
                    self.put(r'\authors{')
                    self.pushstate("authors")
                else:
                    self.put(token)
            elif token == ')':
                if currentstate == "authors":
                    self.popstate()
                    self.put('}')
                else:
                    self.put(token)
            ### _emphasis_
            elif token == '_':
                if currentstate == "emphasis":
                    self.popstate()
                    self.put('}')
                else:
                    self.pushstate("emphasis")
                    self.put(r'\emph{')
            ### *keywords* only avalailable at the beginnig of paragraphs
            elif token == '*':
                if currentstate == "keywordnext":
                    self.popstate()
                    self.put(r'\textbf{')
                    self.pushstate("keyword")
                elif currentstate == "keyword":
                    self.popstate()
                    self.put('}')
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
                        self.put('\n\\item ')
                    else:
                        self.cleanup()
                        self.put('\\begin{itemize}\n\\item ')
                        self.pushstate("list")
                else:
                    self.put(token)
            ### the default case for all the non-special tokens
            ### but escaping the tex special tokens
            else:
                self.putescaped(token)

        ## finally return the result
        return self.result()
