import re

tokenre = re.compile("[}{)(*_-]" + # single chars
                     "|\\${1,2}|\\[{1,2}|\\]{1,2}" + # single/double chars
                     "|[ \t]+|\\n+" + # char groups
                     "|[^][}{)( \t\n$*_-]+", # rest
                     re.UNICODE)

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

    handle_heading = u"[%s]".__mod__
    handle_subheading = u"[[%s]]".__mod__
    handle_ednote = u"{%s}".__mod__
    handle_displaymath = u"$$%1s$$".__mod__
    handle_authors = u"(%s)".__mod__
    handle_paragraph = u"%s".__mod__
    handle_list = u"%s".__mod__
    handle_item = u"- %s".__mod__
    handle_emphasis = u"_%s_".__mod__
    handle_keyword = u"*%s*".__mod__
    handle_inlinemath = u"$%1s$".__mod__
    handle_nestedednote = u"{%s}".__mod__
    handle_seenwhitespace = u"%.0s ".__mod__
    handle_seennewline = u"%.0s\n".__mod__
    handle_wantsnewline = handle_seennewline

    def __init__(self, string, debug=False):
        assert isinstance(string, unicode)
        self.input = [m.string.__getslice__(*m.span())
                      for m in tokenre.finditer(string)]
        self.debug = debug
        self.pos = 0
        self.stack = [ "root", "start" ]
        self.output = [ u"", u"" ]

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
        self.output.append(u"")
        self.stack.append(value)

    def changestate(self, state):
        """
        Change the current state to another state. The caller has to ensure
        that the current state has received no output. Also this change in
        state will not invoke any handle_* methods. It will silently eat the
        current state as if it had never been there.
        @type state: str
        """
        assert isinstance(state, str)
        assert self.output[-1] == u""
        self.stack[-1] = state

    def shiftseennewpardown(self):
        """
        exchange seennewpar on top of the stack with the state below.

        newpars terminate all contexts (except ednotes) via cleanup. But we
        want to emit the newpar only after we closed all other contexts (like
        lists). So we have to push it down the stack.

        We have to do a bit of magic because the seennewpar will receive the
        content of the states which are popped from the stack above it (since we
        push the seennewpar down).
        """
        if not self.lookstate() == "seennewpar":
            return
        ## this is the seennewpar
        stateone = self.stack.pop()
        valueone = self.output.pop()
        ## this is whatever else
        statetwo = self.stack.pop()
        valuetwo = self.output.pop()
        ## push the seennewpar with empty content
        self.pushstate(stateone)
        ## push other state with content which ended up in seennewpar
        ## but were intended for this state
        self.stack.append(statetwo)
        self.output.append(valuetwo + valueone)

    def transposestates(self):
        """
        Exchange the two topmost states of the stack.

        This exchanges the content to, so be careful not to reverse anything.
        """
        stateone = self.stack.pop()
        valueone = self.output.pop()
        statetwo = self.stack.pop()
        valuetwo = self.output.pop()
        self.stack.append(stateone)
        self.output.append(valueone)
        self.stack.append(statetwo)
        self.output.append(valuetwo)

    def poptoken(self):
        """
        get a new token from the input string and advance the position in
        the input string.

        @rtype: char
        @returns: the char at the current position
        @raises IndexError
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
            return u''

    def lookprintabletoken(self):
        """
        view the next non-whitespace token from the input string without
        side effects. If no token is available return an empty string.

        @rtype: char
        @returns: the next char
        """
        try:
            tmp = 0
            while self.input[self.pos + tmp].isspace():
                tmp += 1
            return self.input[self.pos + tmp]
        except IndexError:
            return u''

    def insertwhitespace(self):
        """
        interface for putting whitespace
        """
        self.put(u' ')

    def insertnewline(self):
        """
        interface for putting newlines
        """
        self.put(u'\n')

    def insertnewpar(self):
        """
        interface for putting newpars
        """
        self.put(u'\n\n')

    def put(self, s):
        """
        append s to the output string

        @type s: unicode
        @param s: string to append
        """
        self.output[-1] += s

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
        @param s: string to append
        """
        assert isinstance(s, unicode)
        self.put(s.translate(self.escapemap))

    def cleanup(self):
        """
        close all open states.

        This is triggered by newpars and several other contexts.
        """
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
            elif currentstate in ("seennewline", "wantsnewline"):
                self.popstate()
            elif currentstate == "seennewpar":
                ## push the newpar one step down
                ## this allows to close all other contexts before the newpar
                ## is commited to the output string
                self.shiftseennewpardown()
                ## once we reached the bottom, process the newpar
                if self.lookstate() == "normal":
                    self.transposestates()
                    self.popstate()
                    self.insertnewpar()
            else:
                raise ValueError("invalid state: %s" % currentstate)

    def predictnextstructure(self, token):
        """
        After a newline some future tokens have a special meaning. This
        function is to be called after every newline and marks these tokens
        as active.
        """
        if self.lookstate() in ("inlinemath", "displaymath", "ednote"):
            return
        if token.startswith(u'['):
            self.pushstate("headingnext")
        if token == u'-':
            if self.looktoken()[0:1] in (u' ', u'\t'):
                self.pushstate("listnext")
        if token == u'{':
            self.pushstate("ednotenext")
        if token.startswith(u"$$"):
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
                if token == u'{':
                    self.pushstate("nestedednote")
                elif token == u'}':
                    self.popstate()
                else:
                    self.putescaped(token)
                continue
            if currentstate == "ednote":
                if token == u'{':
                    self.pushstate("nestedednote")
                elif token == u'}':
                    self.popstate()
                    self.pushstate("wantsnewline")
                else:
                    # FIXME regulate escaping
                    # guarante no '\end{ednote}' is contained
                    self.putescaped(token)
                continue

            ## second handle whitespace
            ## we contract whitespace as far as sensible
            if token[0:1] in (u' ', u'\t'):
                if currentstate not in ("start", "seenwhitespace",
                                        "seennewline", "seennewpar",
                                        "wantsnewline"):
                    self.pushstate("seenwhitespace")
                continue
            elif token == u'\n':
                if currentstate == "start" or currentstate == "seennewpar":
                    pass
                elif currentstate == "seenwhitespace":
                    self.changestate("seennewline")
                elif currentstate == "seennewline":
                    self.changestate("seennewpar")
                elif currentstate == "wantsnewline":
                    ## if we want a newline and there is one everything is nice
                    self.changestate("seennewline")
                else:
                    self.pushstate("seennewline")
                continue
            elif token.startswith(u"\n\n"):
                if currentstate == "seenwhitespace":
                    self.changestate("seennewpar")
                elif currentstate == "seennewline":
                    self.changestate("seennewpar")
                elif currentstate == "wantsnewline":
                    ## if we want a newline and there is one everything is nice
                    self.changestate("seennewpar")
                else:
                    self.pushstate("seennewpar")
                continue


            ## now we have a non-whitespace token so we clean up the state
            ## i.e. remove whitespace from the context
            ## a double newline ends all environments (except ednotes)
            if currentstate == "paragraph":
                ## minor optimization, but I feel it is worth it
                ## to shortcircuit this statement
                pass
            elif currentstate == "seenwhitespace":
                self.popstate()
            elif currentstate in ("seennewline", "wantsnewline"):
                self.popstate()
                ## activate special tokens
                self.predictnextstructure(token)
            elif currentstate == "seennewpar":
                ## handling of the seennewpar is done by cleanup
                self.cleanup()
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
            if self.lookstate() in ("inlinemath", "displaymath"):
                ## math special token $
                if token.startswith(u'$'):
                    if currentstate == "inlinemath":
                        self.popstate()
                        self.putescaped(token[1:])
                    else:
                        # displaymath
                        self.popstate()
                        self.pushstate("wantsnewline")
                        self.putescaped(token[2:])
                ## but we still need to escape
                else:
                    self.putescaped(token)
                continue

            ## fourth if a new paragraph is beginning insert it into the context
            if self.lookstate() == "normal":
                self.pushstate("paragraph")
                if token == u'*':
                    self.pushstate("keywordnext")

            ## update current state, since it could be modified
            currentstate = self.lookstate()

            ## fifth now we handle all printable tokens
            ### ednotes as { note to self }
            if token == u'{':
                ## if we are at the beginnig of a line (as advertised by
                ## predictnextstructure) everything is okay, otherwise we
                ## have to insert a newline
                if currentstate == "ednotenext":
                    self.cleanup()
                else:
                    self.cleanup()
                    self.insertnewline()
                self.pushstate("ednote")
            ### math in the forms $inline$ and $$display$$
            elif token == u'$':
                self.pushstate("inlinemath")
            elif token == u"$$":
                ## if we are at the beginnig of a line (as advertised by
                ## predictnextstructure) everything is okay, otherwise we
                ## have to insert a newline
                if currentstate == "displaymathnext":
                    self.cleanup()
                else:
                    self.cleanup()
                    self.insertnewline()
                self.pushstate("displaymath")
            ### [heading] and [[subheading]]
            ### with optional (authors) following
            elif token.startswith(u'['):
                if token == u'[':
                    newstate = "heading"
                    rem = token[1:]
                else:
                    newstate = "subheading"
                    rem = token[2:]
                if currentstate == "headingnext":
                    self.popstate()
                    self.cleanup()
                    self.pushstate(newstate)
                    self.putescaped(rem)
                else:
                    self.putescaped(token)
            elif token.startswith(u']'):
                if currentstate == "heading":
                    self.popstate()
                    token = token[1:]
                    if (not token) and self.lookprintabletoken() == u'(':
                        self.pushstate("authorsnext")
                    self.pushstate("wantsnewline")
                elif token.startswith(u"]]") and currentstate == "subheading":
                    self.popstate()
                    token = token[2:]
                    if (not token) and self.lookprintabletoken() == u'(':
                        self.pushstate("authorsnext")
                    self.pushstate("wantsnewline")
                self.putescaped(token)
            ### (authors) only available after [heading] and [[subheading]]
            elif token == u'(':
                if currentstate == "authorsnext":
                    self.popstate()
                    self.pushstate("authors")
                else:
                    self.put(token)
            elif token == u')':
                if currentstate == "authors":
                    self.popstate()
                    self.pushstate("wantsnewline")
                else:
                    self.put(token)
            ### _emphasis_
            elif token == u'_':
                if currentstate == "emphasis":
                    self.popstate()
                else:
                    self.pushstate("emphasis")
            ### *keywords* only avalailable at the beginnig of paragraphs
            elif token == u'*':
                if currentstate == "keywordnext":
                    self.changestate("keyword")
                elif currentstate == "keyword":
                    self.popstate()
                else:
                    self.put(token)
            ### lists only available at the beginning of lines
            ### - items
            ### - like
            ### - this
            elif token == u'-':
                if currentstate == "listnext":
                    self.popstate()
                    if self.looktoken() == u' ' or self.looktoken() == u'\t':
                        self.poptoken()
                        if self.lookstate() == "item":
                            self.popstate()
                            self.pushstate("item")
                        else:
                            self.cleanup()
                            self.pushstate("list")
                            self.pushstate("item")
                    else:
                        self.put(token)
                else:
                    self.put(token)
            ### the default case for all the non-special tokens
            ### but escaping the special tokens
            else:
                self.putescaped(token)

        ## finally return the result
        return self.result()
