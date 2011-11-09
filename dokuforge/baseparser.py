class BaseParser:
    """
    Base class for parsing Dokuforge Syntax.

    It works by scanning the text one token at a time (with a bit of
    lookahead) and remembering all context in a stack, so the meaning of
    tokens change as the context changes.

    @ivar input: the input string
    @ivar pos: current position in the input string
    @ivar stack: contains the current context
    @ivar output: is a stack of current outputs
    @cvar escapemap: a mapping of characters that need escaping to their
            escaped representation
    """
    escapemap = {}
    def __init__(self, string):
        assert isinstance(string, unicode)
        self.input = string
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

    def result(self):
        """
        @rtype: unicode
        @returns: result string
        """
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
                                  "keyword", "paragraph", "subheading"):
                self.popstate()
            elif currentstate in ("authorsnext", "headingnext", "listnext",
                                  "keywordnext"):
                self.popstate()
            elif currentstate in ("list", "item"):
                self.popstate()
            elif currentstate in ("ednote", "emphasis", "inlinemath",
                                  "nestedednote"):
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

