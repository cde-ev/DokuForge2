# -*- coding: utf-8 -*-

class DokuforgeToHtmlParser:
    """
    Parser for converting Dokuforge Syntax into viewable html.

    It works by scanning the text one token at a time (with a bit of
    lookahead) and remembering all context in a stack, so the meaning of
    tokens change as the context changes.

    @ivar stack: contains the current context
    @ivar pos: current position in the input string
    @ivar input: the input string
    @ivar output: the output string
    @ivar debug: toggles debug output
    """
    def __init__(self, string, debug = False):
        assert isinstance(string, unicode)
        self.stack = [ "start" ]
        self.pos = 0
        self.input = string
        self.output = ''
        self.debug = debug

    def lookstate(self):
        """
        @rtype: str
        @returns: topmost state in the context
        """
        return self.stack[len(self.stack)-1]

    def popstate(self):
        """
        remove a state from the context

        @rtype: str
        @returns: the removed state
        """
        return self.stack.pop()

    def pushstate(self, value):
        """
        put a new state an top of the context
        """
        return self.stack.append(value)

    def poptoken(self):
        """
        get a new token from the input string and advance the position in
        the input string.

        @rtype: char
        @returns: the char at the current position
        @raises: IndexError
        """
        self.pos +=1
        return self.input[self.pos-1]

    def looktoken(self):
        """
        view the next token from the input string without side effects. If
        no token is available return an empty string.

        @rtype: char
        @returns: the next char
        """
        try:
            return self.input[self.pos]
        except IndexError:
            return ''

    def lookprintabletoken(self):
        """
        view the next non-whitespace token from the input string without
        side effects. If no token is available return an empty string.

        @rtype: char
        @returns: the next char
        """
        try:
            tmp = 0
            while self.input[self.pos + tmp] in ' \t\n':
                tmp +=1
            return self.input[self.pos + tmp]
        except IndexError:
            return ''

    def put(self, s):
        """
        append s to the output string

        @type s: unicode
        @value s: string to append
        """
        self.output += s

    def putescaped(self, s):
        """
        append s to the output string escaping html special characters

        @type s: unicode
        @value s: string to append
        """
        for i in range(len(s)):
            token = s[i]
            if token == '<':
                self.put("&lt;")
            elif token == '>':
                self.put("&gt;")
            elif token == '&':
                self.put("&amp;")
            elif token == '"':
                self.put("&quot;")
            else:
                self.put(token)

    def result(self):
        """
        @rtype: unicode
        @returns: result string
        """
        return self.output

    def __str__(self):
        """
        return representation of the current context
        """
        return str(self.stack)

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
                self.put('</h2>\n')
            elif currentstate == "subheading":
                self.popstate()
                self.put('</h3>\n')
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
                self.put('</i>\n')
            elif currentstate == "list":
                self.popstate()
                self.put('</li>\n</ul>\n')
            elif currentstate == "paragraph":
                self.popstate()
                self.put('</p>\n')
            elif currentstate == "emphasis":
                self.popstate()
                self.put('</i>')
            elif currentstate == "keywordnext":
                self.popstate()
                self.put('\n\n')
            elif currentstate == "keyword":
                self.popstate()
                self.put('</b>\n')
            elif currentstate == "ednote":
                self.popstate()
                if not self.lookstate() == "ednote":
                    self.put('</pre>')
            elif currentstate == "inlinmath":
                self.popstate()
                self.put('$')
            elif currentstate == "displaymath":
                self.popstate()
                self.put('$$\n')
            elif currentstate == "seenwhitespace":
                self.popstate()
                self.put(' ')
            elif currentstate == "seennewline":
                self.popstate()
                self.put('\n')
            elif currentstate == "seennewpar":
                self.popstate()
                self.put('\n')
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
                            self.put('$$')
                        else:
                            self.put('$$')
                ## but we still need to escape
                else:
                    self.putescaped(token)
                continue

            ## fourth if a new paragraph is beginning insert it into the context
            if self.lookstate() == "normal":
                self.put('<p>')
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
                    self.put('$$')
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
                        self.put('<h3>')
                        self.pushstate("subheading")
                    else:
                        self.put('<h2>')
                        self.pushstate("heading")
                else:
                    self.put(token)
            elif token == ']':
                if currentstate == "heading":
                    self.popstate()
                    self.put('</h2>')
                    if self.lookprintabletoken() == '(':
                        self.pushstate("authorsnext")
                elif currentstate == "subheading":
                    if self.looktoken() == ']':
                        self.poptoken()
                        self.popstate()
                        self.put('</h3>')
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
                    self.put('<i>')
                    self.pushstate("authors")
                else:
                    self.put(token)
            elif token == ')':
                if currentstate == "authors":
                    self.popstate()
                    self.put('</i>')
                else:
                    self.put(token)
            ### _emphasis_
            elif token == '_':
                if currentstate == "emphasis":
                    self.popstate()
                    self.put('</i>')
                else:
                    self.pushstate("emphasis")
                    self.put('<i>')
            ### *keywords* only avalailable at the beginnig of paragraphs
            elif token == '*':
                if currentstate == "keywordnext":
                    self.popstate()
                    self.put('<b>')
                    self.pushstate("keyword")
                elif currentstate == "keyword":
                    self.popstate()
                    self.put('</b>')
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
        return self.output
