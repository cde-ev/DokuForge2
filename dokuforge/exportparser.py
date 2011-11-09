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

    handle_heading = "\\section{%s}".__mod__
    handle_subheading = "\\subsection{%s}".__mod__
    handle_emphasis = "\\emph{%s}".__mod__
    handle_paragraph = "%s\n\\par\n".__mod__
    handle_authors = "\\authors{%s}".__mod__
    handle_keyword = "\\textbf{%s}".__mod__
    handle_inlinemath = "$%s$".__mod__
    handle_displaymath = "\\[%s\\]".__mod__
    handle_ednote = "\\begin{ednote}%s\end{ednote}".__mod__
    handle_list = "\\begin{itemize}\n%s\end{itemize}".__mod__
    handle_item = "\\item %s\n".__mod__

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
            if currentstate == "nestedednote":
                if token == '{':
                    self.pushstate("nestedednote")
                elif token == '}':
                    self.popstate()
                self.putescaped(token)
                continue
            if currentstate == "ednote":
                if token == '{':
                    self.put('{')
                    self.pushstate("nestedednote")
                elif token == '}':
                    self.popstate()
                    self.put('\n')
                else:
                    # FIME regulate escaping
                    self.putescaped(token)
                continue

            ## second handle whitespace
            ## we contract whitespace as far as sensible
            if token == ' ' or token == '\t':
                if currentstate not in ("start", "seenwhitespace",
                                        "seennewline", "seennewpar"):
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
                self.put('\n')
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
                    if self.lookstate() == "item":
                        self.popstate()
                        self.pushstate("item")
                    else:
                        self.cleanup()
                        self.pushstate("list")
                        self.pushstate("item")
                else:
                    self.put(token)
            ### the default case for all the non-special tokens
            ### but escaping the tex special tokens
            else:
                self.putescaped(token)

        ## finally return the result
        return self.result()
