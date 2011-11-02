# -*- coding: utf-8 -*-

class DokuforgeToHtmlParser:
    def __init__(self, string, debug = False):
        assert isinstance(string, unicode)
        self.stack = [ "start" ]
        self.pos = 0
        self.input = string
        self.output = ''
        self.debug = debug

    def look(self):
        return self.stack[len(self.stack)-1]
    def pop(self):
        return self.stack.pop()
    def append(self, value):
        return self.stack.append(value)
    def nexttoken(self):
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
        while not self.look() == "normal":
            currentstate = self.look()
            if currentstate == "start":
                self.pop()
                self.append("normal")
            elif currentstate == "heading":
                self.pop()
                self.put('</h2>\n')
            elif currentstate == "subheading":
                self.pop()
                self.put('</h3>\n')
            elif currentstate == "authorsnext":
                self.pop()
                self.put('\n\n')
            elif currentstate == "headingnext":
                self.pop()
                self.put('\n\n')
            elif currentstate == "listnext":
                self.pop()
                self.put('\n\n')
            elif currentstate == "authors":
                self.pop()
                self.put('</i>\n')
            elif currentstate == "list":
                self.pop()
                self.put('</li>\n</ul>\n')
            elif currentstate == "paragraph":
                self.pop()
                self.put('</p>\n')
            elif currentstate == "emphasis":
                self.pop()
                self.put('</i>')
            elif currentstate == "keywordnext":
                self.pop()
                self.put('\n\n')
            elif currentstate == "keyword":
                self.pop()
                self.put('</b>\n')
            elif currentstate == "ednote":
                self.pop()
                if not self.look() == "ednote":
                    self.put('</pre>')
            elif currentstate == "seenwhitespace":
                self.pop()
                self.put(' ')
            elif currentstate == "seennewline":
                self.pop()
                self.put('\n')
            elif currentstate == "seennewpar":
                self.pop()
                self.put('\n')
            else:
                pass
    def fortune(self, token):
        if token == '[':
            self.append("headingnext")
        if token == '-':
            self.append("listnext")

    def parse(self):
        while True:
            ## retrieve token
            try:
                token = self.nexttoken()
            except IndexError:
                self.cleanup()
                break
            ## retrieve current state
            currentstate = self.look()
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
                    self.append("ednote")
                    self.put('{')
                elif token == '}':
                    self.pop()
                    if self.look() == "ednote":
                        self.put('}')
                    else:
                        self.put('</pre>\n')
                else:
                    self.put(token)
                continue
            elif token == '{':
                self.cleanup()
                self.append("ednote")
                self.put('<pre>')
                continue
            ## now handle everything else
            ### first handle whitespace
            if token == ' ' or token == '\t':
                if currentstate == "start" or currentstate == "seenwhitespace" or \
                       currentstate == "seennewline" or currentstate == "seennewpar":
                    pass
                else:
                    self.append("seenwhitespace")
                continue
            elif token == '\n':
                if currentstate == "start" or currentstate == "seennewpar":
                    pass
                elif currentstate == "seenwhitespace":
                    self.pop()
                    self.append("seennewline")
                elif currentstate == "seennewline":
                    self.pop()
                    self.append("seennewpar")
                else:
                    self.append("seennewline")
                continue
            ### now we have a non-whitespace token so we clean up the self
            if currentstate == "paragraph":
                ## minor optimization, but I feel it is worth it
                ## to shortcircuit this selfment
                pass
            elif currentstate == "seenwhitespace":
                self.pop()
                self.put(' ')
            elif currentstate == "seennewline":
                self.pop()
                self.put('\n')
                self.fortune(token)
            elif currentstate == "seennewpar":
                self.pop()
                self.cleanup()
                self.put('\n')
                self.fortune(token)
            elif currentstate == "start":
                self.pop()
                self.append("normal")
                self.fortune(token)

            ### if a new paragraph is beginning
            if self.look() == "normal":
                self.put('<p>')
                self.append("paragraph")
                if token == '*':
                    self.append("keywordnext")

            ## update current state, since it could be modified by the white
            ## space handling
            currentstate = self.look()

            ### now we handle all printable tokens
            if token == '[':
                if currentstate == "headingnext":
                    self.pop()
                    self.cleanup()
                    if self.looktoken() == '[':
                        self.nexttoken()
                        self.put('<h3>')
                        self.append("subheading")
                    else:
                        self.put('<h2>')
                        self.append("heading")
                else:
                    self.put(token)
            elif token == ']':
                if currentstate == "heading":
                    self.pop()
                    self.put('</h2>\n')
                    if self.lookprintabletoken() == '(':
                        self.append("authorsnext")
                elif currentstate == "subheading":
                    if self.looktoken() == ']':
                        self.nexttoken()
                        self.pop()
                        self.put('</h3>\n')
                        if self.lookprintabletoken() == '(':
                            self.append("authorsnext")
                    else:
                        self.put(token)
                else:
                    self.put(token)
            elif token == '(':
                if currentstate == "authorsnext":
                    self.pop()
                    self.put('<i>')
                    self.append("authors")
                else:
                    self.put(token)
            elif token == ')':
                if currentstate == "authors":
                    self.pop()
                    self.put('</i>\n')
                else:
                    self.put(token)
            elif token == '_':
                if currentstate == "emphasis":
                    self.pop()
                    self.put('</i>')
                else:
                    self.append("emphasis")
                    self.put('<i>')
            elif token == '*':
                if currentstate == "keywordnext":
                    self.pop()
                    self.put('<b>')
                    self.append("keyword")
                elif currentstate == "keyword":
                    self.pop()
                    self.put('</b>')
                else:
                    self.put(token)
            elif token == '-':
                if currentstate == "listnext":
                    self.pop()
                    if self.look() == "list":
                        self.put('</li>\n<li>')
                    else:
                        self.cleanup()
                        self.put('<ul>\n<li>')
                        self.append("list")
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

