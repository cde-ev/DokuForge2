# -*- coding: utf-8 -*-

class ParseLeaf:
    def __init__(self, ident, data):
        self.ident = ident
        self.data = data

    def isactive(self):
        return False

    def display(self, indent=0, verbose=False):
        if not verbose:
            return
        whitespace = u""
        for i in range(indent):
            whitespace += u"    "
        print whitespace + u"ParseLeaf: " + self.ident.encode("utf8") + u" (" + self.data.encode("utf8") + u")"

class ParseTree:
    def __init__(self, ident):
        self.tree = []
        self.active = True
        self.ident = ident

    def isactive(self):
        return self.active

    def insert(self, newtree):
        assert self.active
        if len(self.tree) == 0:
            self.tree.append(newtree)
            return
        if self.tree[-1].isactive():
            self.tree[-1].insert(newtree)
        else:
            self.tree.append(newtree)

    def close(self):
        assert self.active
        if len(self.tree) == 0:
            self.active = False
            return self.ident
        if self.tree[-1].isactive():
            return self.tree[-1].close()
        else:
            self.active = False
            return self.ident

    def display(self, indent=0, verbose=False):
        whitespace = u""
        marker = u""
        for i in range(indent):
            whitespace += u"    "
        if self.isactive():
            marker = u"*"
        print whitespace + u"ParseTree: " + self.ident + marker
        for x in self.tree:
            x.display(indent + 1, verbose)

    def lookstate(self):
        assert self.active
        if len(self.tree) == 0:
            return self.ident
        if self.tree[-1].isactive():
            return self.tree[-1].lookstate()
        else:
            return self.ident

    def lookactiveleaf(self):
        assert self.active
        if len(self.tree) == 0:
            return None
        if isinstance(self.tree[-1], ParseTree):
            if self.tree[-1].active:
                return self.tree[-1].lookactiveleaf()
            else:
                return None
        else:
            return self.tree[-1]

    def appendtoleaf(self, s):
        assert self.active
        assert not len(self.tree) == 0
        if isinstance(self.tree[-1], ParseTree):
            assert self.tree[-1].active
            self.tree[-1].appendtoleaf(s)
        else:
            self.tree[-1].data += s


class TreeParser:
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
    """
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

    def __init__(self, string, debug=False):
        assert isinstance(string, unicode)
        self.input = string
        self.debug = debug
        self.pos = 0
        self.stack = [ "start" ]
        self.tree = ParseTree("root")
        self.output = u""

    def lookstate(self):
        """
        @rtype: str
        @returns: topmost state in the context
        """
        if len(self.stack) == 0:
            return self.tree.lookstate()
        else:
            return self.stack[-1]

    def popstate(self):
        """
        remove a state from the context

        @rtype: str
        @returns: the removed state
        """
        if len(self.stack) == 0:
            return self.tree.close()
        else:
            state = self.stack.pop()
            if state == "seenwhitespace":
                self.tree.insert(ParseLeaf("Whitespace", u" "))
            elif state in ("seennewline", "wantsnewline"):
                self.tree.insert(ParseLeaf("Newline", u"\n"))
            elif state == "seennewpar":
                self.tree.insert(ParseLeaf("Newpar", u"\n\n"))

    def pushstate(self, value):
        """
        put a new state an top of the context
        """
        if value in ("seenwhitespace", "seennewline", "seennewpar", "headingnext", "listnext", "ednotenext", "displaymathnext", "authorsnext", "wantsnewline", "keywordnext"):
            self.stack.append(value)
        else:
            self.tree.insert(ParseTree(value))

    def changestate(self, state):
        """
        Change the current state to another state. The caller has to ensure
        that the current state has received no output. Also this change in
        state will not invoke any handle_* methods. It will silently eat the
        current state as if it had never been there.
        @type state: str
        """
        assert not len(self.stack) == 0
        self.stack[-1] = state

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
            while self.input[self.pos + tmp] in u' \t\n':
                tmp += 1
            return self.input[self.pos + tmp]
        except IndexError:
            return u''

    def insertnewline(self):
        """
        interface for putting newlines
        """
        self.tree.insert(ParseLeaf("Newline", u"\n"))

    def put(self, s):
        """
        append s to the output string

        @type s: unicode
        @param s: string to append
        """
        if not self.lookstate() in ("inlinemath", "displaymath", "ednote", "nestedednote"):
            if s in u'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZäüößÄÖÜ':
                leaf = self.tree.lookactiveleaf()
                if leaf is None or not leaf.ident == "Word":
                    self.tree.insert(ParseLeaf("Word", s))
                else:
                    self.tree.appendtoleaf(s)
            elif s in u'0123456789':
                leaf = self.tree.lookactiveleaf()
                if leaf is None or not leaf.ident == "Number":
                    self.tree.insert(ParseLeaf("Number", s))
                else:
                    self.tree.appendtoleaf(s)
            else:
                self.tree.insert(ParseLeaf("Token", s))
        else:
            self.tree.insert(ParseLeaf("Token", s))

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

    def cleanup(self):
        """
        close all open states.

        This is triggered by newpars and several other contexts.
        """
        while not self.lookstate() == "root":
            currentstate = self.lookstate()
            if currentstate == "start":
                self.popstate()
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
                if self.tree.lookstate() == "root":
                    self.popstate()
                else:
                    self.tree.close()
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
        if token == u'[':
            self.pushstate("headingnext")
        if token == u'-' and self.looktoken() in (u' ', u'\t'):
            self.pushstate("listnext")
        if token == u'{':
            self.pushstate("ednotenext")
        if token == u'$' and self.looktoken() == u'$':
            self.pushstate("displaymathnext")

    def deletetrailingwhitespace(self, tree=None):
        if tree is None:
            tree = self.tree
        if isinstance(tree, ParseLeaf):
            return
        if len(tree.tree) == 0:
            return
        while tree.tree[-1].ident == "Whitespace":
            tree.tree.pop()
            if len(tree.tree) == 0:
                return
        for x in tree.tree:
            self.deletetrailingwhitespace(x)

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
                self.tree.display()
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
                    self.put(token)
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
                    self.put(token)
                continue

            ## second handle whitespace
            ## we contract whitespace as far as sensible
            if token in (u' ', u'\t'):
                if currentstate not in ("start", "seenwhitespace",
                                        "seennewline", "seennewpar",
                                        "wantsnewline"):
                    self.pushstate("seenwhitespace")
                continue
            elif token == u'\n':
                if currentstate in ("start", "seennewpar"):
                    pass
                elif currentstate in ("seenwhitespace", "wantsnewline"):
                    ## if we want a newline and there is one everything is nice
                    self.changestate("seennewline")
                elif currentstate == "seennewline":
                    self.changestate("seennewpar")
                else:
                    self.pushstate("seennewline")
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
                ## activate special tokens
                self.predictnextstructure(token)

            ## third handle math
            ## this deactivates all other special characters
            ## even ednotes since math needs curly braces
            if self.lookstate() in ("inlinemath", "displaymath"):
                ## math special token $
                if token == u'$':
                    if currentstate == "inlinemath":
                        self.popstate()
                    else:
                        # displaymath
                        self.popstate()
                        if self.looktoken() == u'$':
                            self.poptoken()
                        self.pushstate("wantsnewline")
                ## but we still need to escape
                else:
                    self.put(token)
                continue

            ## fourth if a new paragraph is beginning insert it into the context
            if self.lookstate() == "root":
                self.pushstate("paragraph")
                if token == u'*':
                    self.pushstate("keywordnext")

            ## update current state, since it could be modified
            currentstate = self.lookstate()

            ## fifth now we handle all printable tokens
            ### ednotes as { note to self }
            if token == u'{':
                self.cleanup()
                ## if we are at the beginnig of a line (as advertised by
                ## predictnextstructure) everything is okay, otherwise we
                ## have to insert a newline
                ## currentstate is unchanged by self.cleanup
                if not currentstate == "ednotenext":
                    self.insertnewline()
                self.pushstate("ednote")
            ### math in the forms $inline$ and $$display$$
            elif token == u'$':
                if self.looktoken() == u'$':
                    self.poptoken()
                    self.cleanup()
                    ## if we are at the beginnig of a line (as advertised by
                    ## predictnextstructure) everything is okay, otherwise we
                    ## have to insert a newline
                    ## currentstate is unchanged by self.cleanup
                    if not currentstate == "displaymathnext":
                        self.insertnewline()
                    self.pushstate("displaymath")
                else:
                    self.pushstate("inlinemath")
            ### [heading] and [[subheading]]
            ### with optional (authors) following
            elif token == u'[' and currentstate == "headingnext":
                self.popstate()
                self.cleanup()
                if self.looktoken() == u'[':
                    self.poptoken()
                    self.pushstate("subheading")
                else:
                    self.pushstate("heading")
            elif token == u']' and currentstate in ("heading", "subheading"):
                if currentstate == "heading":
                    self.popstate()
                    ## activate paren
                    if self.lookprintabletoken() == u'(':
                        self.pushstate("authorsnext")
                    self.pushstate("wantsnewline")
                elif currentstate == "subheading" and self.looktoken() == u']':
                    self.poptoken()
                    self.popstate()
                    ## activate paren
                    if self.lookprintabletoken() == u'(':
                        self.pushstate("authorsnext")
                    self.pushstate("wantsnewline")
                else:
                    self.put(token)
            ### (authors) only available after [heading] and [[subheading]]
            elif token == u'(' and currentstate == "authorsnext":
                self.popstate()
                self.pushstate("authors")
            elif token == u')' and currentstate == "authors":
                self.popstate()
                self.pushstate("wantsnewline")
            ### _emphasis_
            elif token == u'_':
                if currentstate == "emphasis":
                    self.popstate()
                else:
                    self.pushstate("emphasis")
            ### *keywords* only avalailable at the beginnig of paragraphs
            elif token == u'*' and currentstate in ("keywordnext", "keyword"):
                if currentstate == "keywordnext":
                    self.changestate("keyword")
                else: # keyword
                    self.popstate()
            ### lists only available at the beginning of lines
            ### - items
            ### - like
            ### - this
            elif token == u'-' and currentstate == "listnext" and \
                    self.looktoken() in (u' ', u'\t'):
                self.popstate()
                self.poptoken()
                if self.lookstate() == "item":
                    self.popstate()
                else:
                    self.cleanup()
                    self.pushstate("list")
                self.pushstate("item")
            ### the default case for all the non-special tokens
            ### but escaping the special tokens
            else:
                self.put(token)

        self.deletetrailingwhitespace()

        self.tree.close()

        ## finally return the tree
        return self.tree

    def generateoutput(self, tree=None):
        root = False
        if tree is None:
            tree = self.tree
            root = True
        if isinstance(tree, ParseLeaf):
            return tree.data
        output = u""
        for x in tree.tree:
            value = self.generateoutput(x)
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        if root:
            self.output = output
        return output
