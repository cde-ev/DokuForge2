# -*- coding: utf-8 -*-

class State:
    def __init__(self, string):
        assert isinstance(string, unicode)
        self.stack = [ "start" ]
        self.pos = 0
        self.input = string
        self.output = ''

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
        return self.input[self.pos]
    def lookprintabletoken(self):
        tmp = 0
        while self.input[self.pos + tmp] in ' \t\n':
            tmp +=1
        return self.input[self.pos + tmp]

    def put(self, s):
        self.output += s

    def result(self):
        return self.output

    def __str__(self):
        return str(self.stack)


state = State(u"""

  [Eine Ueberschrift]
(Autor, Korrektor und Chef)

 Lorem  囲碁  ipsum dolor sit amet, consectetur adipiscing elit. Nullam vel dui
mi. Mauris feugiat erat eget quam varius eu congue lectus viverra. Ut sed
  velit dapibus eros ultricies blandit a in felis. Nam ultricies pharetra
luctus. Nam aliquam lobortis rutrum. Phasellus quis arcu non dui pretium
  aliquam. Phasellus id mauris mauris, quis lobortis justo.

 Cras eget lectus urna. Pellentesque lobortis turpis sed nibh ultricies  
  fermentum. Integer iaculis tempus nisl, eget luctus orci varius  
   volutpat. Cras condimentum facilisis scelerisque. Nullam eget tortor ipsum,  
    in rhoncus mi. Sed nec odio sem. Aenean rutrum, dui vel vehicula pulvinar,  
     purus magna euismod dui, id pharetra libero mauris nec dolor. 

[Eine zweite Ueberschrift]
[[Eine Unterueberschrift]]

(Douglas Adams)

Fermats letzter Satz sagt, dass die Gleichung $x^n+y^n = z^n$ fuer $n\ge3$
keine ganzzahlige Loesung, auszer den trivialen, besitzt. Dies war ein
_lange_ Zeit unbewiesenes Theorem. Hier nun eine Liste von interessanten
Zahlen.

$$e^{i\pi}+1=0$$

Aber *Null* war lange Zeit gar keine Zahl. Nam ultricies pharetra
luctus. Nam aliquam lobortis rutrum. Phasellus quis arcu non dui pretium
aliquam. Phasellus id mauris mauris, quis lobortis justo.

*Zweiundvierzig* ist eine Zahl die als Antwort sehr beliebt ist. Nullam eget
tortor ipsum, in rhoncus mi. Sed nec odio sem. Aenean rutrum, dui vel
vehicula pulvinar, purus magna euismod dui, id pharetra libero mauris nec
dolor.

Bitte Escape mich: <>&" und das wars auch schon.

[[Eine weitere Unterueberschrift]]

Wir packen unsere Koffer und nehmen mit
- einen Sonnenschirm, Kapazitaet 3000000 kWh was eine sehr grosze Zahl ist,
    aber zum Glueck noch auf diesen Absatz passt
- Wanderschuhe, Fassungsvermoegen 2 l
- Huepfeseil, Laenge 1 m$^2$
- Plueschkrokodil, Flauschigkeit 79%

Dies schreiben wir auf den Seiten 5--7 in die Tabelle. Dabei geht es --
anders als in so mancher andrer Uebung -- nicht ums blosze wiederholen. Und
so sagte schon Goethe "auch aus Steinen die einem in den Weg gelegt werden,
kann man schoenes bauen", wollen wir uns also ein Beispiel nehmen. Und jetzt
machen wir noch einen Gedankensprung -- schon sind wir auf einem anderen
Planeten.

Man kann z.B. auch ganz viele Abkuerzungen u.a. unterbringen um lange
Absaetze (s.o.) zu stutzen, aber das ist nur ca. halb so leserlich. Auch
nicht besser wird es wenn man ganz viele AKRONYME verwendet ... Aber
manchmal kann es auch nuetzlich sein, so bei ABBILDUNG:zwei gesehen.

{ Hier noch ein Hinweis in verbatim,

  mit einer Leerzeile und { nested braces }. }


""")



def cleanup(state):
    while not state.look() == "normal":
        if state.look() == "heading":
            state.pop()
            state.put('</h2>\n')
        elif state.look() == "subheading":
            state.pop()
            state.put('</h3>\n')
        elif state.look() == "authorsnext":
            state.pop()
            state.put('\n\n')
        elif state.look() == "listnext":
            state.pop()
            state.put('\n\n')
        elif state.look() == "authors":
            state.pop()
            state.put('</i>\n')
        elif state.look() == "list":
            state.pop()
            state.put('</li>\n</ul>\n')
        elif state.look() == "paragraph":
            state.pop()
            state.put('</p>\n')
        elif state.look() == "emphasis":
            state.pop()
            state.put('</i>')
        elif state.look() == "keywordnext":
            state.pop()
            state.put('\n\n')
        elif state.look() == "keyword":
            state.pop()
            state.put('</b>\n')
        elif state.look() == "ednote":
            state.pop()
            if not state.look() == "ednote":
                state.put('</pre>')
        elif state.look() == "seenwhitespace":
            state.pop()
            state.put(' ')
        elif state.look() == "seennewline":
            state.pop()
            state.put('\n')
        elif state.look() == "seennewpar":
            state.pop()
            state.put('\n\n')
        else:
            pass


while True:
    ## retrieve token
    try:
        token = state.nexttoken()
    except IndexError:
        cleanup(state)
        break
    print state
    try:
        print "Token:", token
    except UnicodeEncodeError:
        print "Token: <???> unicode token"
    ## process the token
    ## first handle ednotes
    if state.look() == "ednote":
        if token == '{':
            state.append("ednote")
            state.put('{')
        elif token == '}':
            state.pop()
            if state.look() == "ednote":
                state.put('}')
            else:
                state.put('</pre>\n')
        else:
            state.put(token)
        continue
    elif token == '{':
        cleanup(state)
        state.append("ednote")
        state.put('<pre>')
        continue
    ## now handle everything else
    ### first handle whitespace
    if token == ' ' or token == '\t':
        if state.look() == "start" or state.look() == "seenwhitespace" or \
               state.look() == "seennewline" or state.look() == "seennewpar":
            pass
        else:
            state.append("seenwhitespace")
        continue
    elif token == '\n':
        if state.look() == "start" or state.look() == "seennewpar":
            pass
        elif state.look() == "seenwhitespace":
            state.pop()
            state.append("seennewline")
        elif state.look() == "seennewline":
            state.pop()
            state.append("seennewpar")
        else:
            state.append("seennewline")
        continue
    ### now we have a non-whitespace token so we clean up the state
    if state.look() == "normal" or state.look() == "paragraph":
        ## minor optimization, but I feel it is worth it
        ## to shortcircuit this statement
        pass
    elif state.look() == "seenwhitespace":
        state.pop()
        state.put(' ')
    elif state.look() == "seennewline":
        state.pop()
        state.put('\n')
        if token == '-':
            state.append("listnext")
    elif state.look() == "seennewpar":
        state.pop()
        cleanup(state)
        state.put('\n')
        if token == '-':
            state.append("listnext")
    elif state.look() == "start":
        state.pop()
        state.append("normal")

    ### if a new paragraph is beginning
    if state.look() == "normal":
        if token not in '[':
            state.put('<p>')
            state.append("paragraph")
            if token == '*':
                state.append("keywordnext")

    ### now we handle all printable tokens
    if token == '[':
        if state.looktoken() == '[':
            if state.look() == "normal":
                state.nexttoken()
                state.put('<h3>')
                state.append("subheading")
            else:
                state.put(token)
        else:
            if state.look() == "normal":
                state.put('<h2>')
                state.append("heading")
            else:
                state.put(token)
    elif token == ']':
        if state.look() == "heading":
            state.pop()
            state.put('</h2>\n')
            if state.lookprintabletoken() == '(':
                state.append("authorsnext")
        elif state.look() == "subheading":
            if state.looktoken() == ']':
                state.nexttoken()
                state.pop()
                state.put('</h3>\n')
                if state.lookprintabletoken() == '(':
                    state.append("authorsnext")
            else:
                state.put(token)
        else:
            state.put(token)
    elif token == '(':
        if state.look() == "authorsnext":
            state.pop()
            state.put('<i>')
            state.append("authors")
        else:
            state.put(token)
    elif token == ')':
        if state.look() == "authors":
            state.pop()
            state.put('</i>\n')
        else:
            state.put(token)
    elif token == '_':
        if state.look() == "emphasis":
            state.pop()
            state.put('</i>')
        else:
            state.append("emphasis")
            state.put('<i>')
    elif token == '*':
        if state.look() == "keywordnext":
            state.pop()
            state.put('<b>')
            state.append("keyword")
        elif state.look() == "keyword":
            state.pop()
            state.put('</b>')
        else:
            state.put(token)
    elif token == '-':
        if state.look() == "listnext":
            state.pop()
            if state.look() == "list":
                state.put('</li>\n<li>')
            else:
                if state.look() == "paragraph":
                   state.pop()
                   state.put('</p>\n')
                state.put('<ul>\n<li>')
                state.append("list")
        else:
            state.put(token)
    elif token == '<':
        state.put("&lt;")
    elif token == '>':
        state.put("&gt;")
    elif token == '&':
        state.put("&amp;")
    elif token == '"':
        state.put("&quot;")
    else:
        state.put(token)

print state.result().encode("utf8")

