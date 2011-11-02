# -*- coding: utf-8 -*-

class DokuforgeToHtmlParser:
    def __init__(self, string, debug = False):
        assert isinstance(string, unicode)
        self.stack = [ "start" ]
        self.pos = 0
        self.input = string
        self.output = ''
        self.debug = debug

    def lookstate(self):
        return self.stack[len(self.stack)-1]
    def popstate(self):
        return self.stack.pop()
    def pushstate(self, value):
        return self.stack.append(value)
    def poptoken(self):
        self.pos +=1
        return self.input[self.pos-1]
    def looktoken(self):
        try:
            return self.input[self.pos]
        except IndexError:
            return ''
    def lookprintabletoken(self):
        try:
            tmp = 0
            while self.input[self.pos + tmp] in ' \t\n':
                tmp +=1
            return self.input[self.pos + tmp]
        except IndexError:
            return ''

    def put(self, s):
        self.output += s

    def result(self):
        return self.output

    def __str__(self):
        return str(self.stack)

    def cleanup(self):
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
        if token == '[':
            self.pushstate("headingnext")
        if token == '-':
            self.pushstate("listnext")

    def parse(self):
        while True:
            ## retrieve token
            try:
                token = self.poptoken()
            except IndexError:
                self.cleanup()
                break
            ## retrieve current state
            currentstate = self.lookstate()
            if self.debug:
                print self
                try:
                    print "Token:", token
                except UnicodeEncodeError:
                    print "Token: <???> unicode token"
            ## process the token
            ## first handle ednotes
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
                    self.put(token)
                continue
            elif token == '{':
                self.cleanup()
                self.pushstate("ednote")
                self.put('<pre>')
                continue
            ## now handle everything else
            ### first handle whitespace
            if token == ' ' or token == '\t':
                if currentstate == "start" or currentstate == "seenwhitespace" or \
                       currentstate == "seennewline" or currentstate == "seennewpar":
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
            ### now we have a non-whitespace token so we clean up the self
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
                self.predictnextstructure(token)
            elif currentstate == "seennewpar":
                self.popstate()
                self.cleanup()
                self.put('\n')
                self.predictnextstructure(token)
            elif currentstate == "start":
                self.popstate()
                self.pushstate("normal")
                self.predictnextstructure(token)

            ### if a new paragraph is beginning
            if self.lookstate() == "normal":
                self.put('<p>')
                self.pushstate("paragraph")
                if token == '*':
                    self.pushstate("keywordnext")

            ## update current state, since it could be modified by the white
            ## space handling
            currentstate = self.lookstate()

            ### now we handle all printable tokens
            if token == '[':
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
                            self.pushstate("authorsnext")
                    else:
                        self.put(token)
                else:
                    self.put(token)
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
            elif token == '_':
                if currentstate == "emphasis":
                    self.popstate()
                    self.put('</i>')
                else:
                    self.pushstate("emphasis")
                    self.put('<i>')
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
            elif token == '<':
                self.put("&lt;")
            elif token == '>':
                self.put("&gt;")
            elif token == '&':
                self.put("&amp;")
            elif token == '"':
                self.put("&quot;")
            else:
                self.put(token)
        return self.output

