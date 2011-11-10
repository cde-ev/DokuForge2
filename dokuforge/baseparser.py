from dokuforge.common import end_with_newline

class BaseParser:
    """
    Base class for parsing Dokuforge Syntax.

    It works by scanning the text one token at a time (with a bit of
    lookahead) and remembering all context in a stack, so the meaning of
    tokens change as the context changes.

    @ivar input: the input string
    @ivar debug: toggles debug output
    @ivar pos: current position in the input string
    @ivar stack: contains the current context
    @ivar output: is a stack of current outputs
    @cvar escapemap: a mapping of characters that need escaping to their
            escaped representation
    """
    escapemap = {}
    handle_ednote = lambda self, data: self.do_block(data, "{%s}")
    handle_paragraph = lambda self, data: self.do_block(data, "%s")
    handle_list = lambda self, data: self.do_environ(data, "%s")
    handle_item = lambda self, data: self.do_block(data, "- %s")
    handle_displaymath = lambda self, data: self.do_block(data, "$$%s$$")
    handle_authors = lambda self, data: self.do_block(data, "(%s)")
    handle_heading = lambda self, data: self.do_block(data, "[%s]")
    handle_subheading = lambda self, data: self.do_block(data, "[[%s]]")
    handle_emphasis = "_%s_".__mod__
    handle_keyword = "*%s*".__mod__
    handle_inlinemath = "$%s$".__mod__

    def __init__(self, string, debug=False):
        assert isinstance(string, unicode)
        self.input = string
        self.debug = debug
        self.pos = 0
        self.stack = [ "root", "start" ]
        self.output = [ "", "" ]

    def lookstate(self):
        """
        @rtype: str
        @returns: topmost state in the context
        """
        return self.stack[-1]

    def popstate(self):
        """
        remove a state from the context

        @rtype: str
        @returns: the removed state
        """
        state = self.stack.pop()
        value = self.output.pop()
        try:
            handler = getattr(self, "handle_%s" % state)
        except AttributeError:
            pass
        else:
            value = handler(value)
        self.put(value)
        return state

    def pushstate(self, value):
        """
        put a new state an top of the context
        """
        self.output.append("")
        self.stack.append(value)

    def poptoken(self):
        """
        get a new token from the input string and advance the position in
        the input string.

        @rtype: char
        @returns: the char at the current position
        @raises: IndexError
        """
        self.pos += 1
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
                tmp += 1
            return self.input[self.pos + tmp]
        except IndexError:
            return ''

    def put(self, s):
        """
        append s to the output string

        @type s: unicode
        @value s: string to append
        """
        self.output[-1] += s

    def ensurenewline(self):
        """
        Ensure that the last token in the output is a newline.

        This is intended to insert a newline for better formatting of the
        output text whenever no newline was input by the user.
        """
        ## we walk the stack from top to bottom
        stackpos = -1
        while stackpos > -len(self.output):
            try:
                if not self.output[stackpos][-1] == '\n':
                    self.put('\n')
                    return
                else:
                    return
            ## there might be an IndexError if the topmost entrys in the stack
            ## are empty strings, thus recurse
            except IndexError:
                stackpos -= 1
        ## if we have nothing yet, we do nothing
        ## this prevents inserting a silly newline at the start of the result

    def ensurenewpar(self):
        """
        Ensure that the two last token in the output are newlines.

        This is intended to insert a new par for better formatting of the
        output text whenever no new par was input by the user.
        """
        ## we walk the stack from top to bottom
        stackpos = -1
        ## we need to keep track whether we already found a newline or not
        foundone = False
        while stackpos > -len(self.output):
            try:
                if not self.output[stackpos][-1] == '\n':
                    if not foundone:
                        self.put('\n\n')
                    else:
                        self.put('\n')
                    return
                else:
                    foundone = True
                    if not self.output[stackpos][-2] == '\n':
                        self.put('\n')
                        return
                    else:
                        return
            ## there might be an IndexError if the topmost entrys in the stack
            ## are near empty strings, thus recurse
            except IndexError:
                stackpos -= 1
        ## if we have nothing yet, we do nothing
        ## this prevents inserting a silly new par at the start of the result

    def do_block(self, data, pattern):
        """
        helper function for the actual parsers

        Ensure that the block begins on a new line of itself.
        """
        self.ensurenewline()
        return pattern % data

    def do_environ(self, data, pattern):
        """
        helper function for the actual parsers

        Ensure that the environment begins on a new line of itself and
        the closing is on a line of itself too.
        """
        self.ensurenewline()
        return pattern % end_with_newline(data)

    def result(self):
        """
        Return the result. This tries to apply self.postprocessor which gives
        a hook to filter the result one more time.

        @rtype: unicode
        @returns: result string
        """
        try:
            return self.postprocessor(self.output[-1])
        except AttributeError:
            return self.output[-1]

    def __str__(self):
        """
        return representation of the current context
        """
        return str(self.stack)

    def putescaped(self, s):
        """
        append s to the output string escaping special characters

        @type s: unicode
        @value s: string to append
        """
        assert isinstance(s, unicode)
        for token in s:
            self.put(self.escapemap.get(token, token))

    def cleanup(self):
        """
        close all open states
        """
        pars = 0
        while not self.lookstate() == "normal":
            currentstate = self.lookstate()
            if currentstate == "start":
                self.popstate()
                self.pushstate("normal")
            elif currentstate in ("authors", "displaymath", "heading",
                                  "keyword", "paragraph", "subheading",
                                  "authorsnext", "headingnext", "listnext",
                                  "keywordnext", "ednotenext",
                                  "displaymathnext", "list", "item", "ednote",
                                  "emphasis", "inlinemath", "nestedednote"):
                self.popstate()
            elif currentstate == "seenwhitespace":
                self.popstate()
                self.put(' ')
            elif currentstate == "seennewline":
                self.popstate()
                if pars < 1:
                    pars = 1
            elif currentstate == "seennewpar":
                self.popstate()
                pars = 2
            else:
                raise ValueError("invalid state")
        for i in range(pars):
            self.put('\n')

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
        if token == '{':
            self.pushstate("ednotenext")
        if token == '$':
            if self.looktoken() == '$':
                self.pushstate("displaymathnext")

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
                else:
                    # FIXME regulate escaping
                    # guarante no '\end{ednote}' is contained
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
                self.put('\n\n')
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
            ### math in the forms $inline$ and $$display$$
            elif token == '$':
                if self.looktoken() == '$':
                    self.poptoken()
                    self.cleanup()
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
            ### but escaping the special tokens
            else:
                self.putescaped(token)

        ## finally return the result
        return self.result()
