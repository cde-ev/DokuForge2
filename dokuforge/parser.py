import re

def isemptyline(line):
    return re.match('^[ \t]*$', line)

class PTree:
    """
    Abstract class where all parsed objects inherit from.
    """
    def debug(self):
        return None

    def isEmpty(self):
        return False

class PSequence(PTree):
    """
    A piece of text formed by juxtaposition of several
    Parse Trees (usually paragraphs).
    """
    def __init__(self, parts):
        self.parts = parts

    def debug(self):
        return ('Sequence', [part.debug() for part in self.parts])

class PLeaf(PTree):
    """
    A piece of text that contains no further substructure.
    """
    def __init__(self, text):
        self.text = text

    def debug(self):
        return self.text

    def isEmpty(self):
        return isemptyline(self.text)

class PEmph(PTree):
    """
    An emphasized piece of text.
    """
    def __init__(self, text):
        self.text = text

    def debug(self):
        return ('emph', self.text)

class PEdnote(PTree):
    """
    An Ednote; contents are compeletly unchanged.
    """
    def __init__(self, text):
        self.text = text

    def isEmpty(self):
        # the mere fact that there was an Ednote
        # is already worth mentioning
        return False

    def debug(self):
        return ('Ednote', self.text)

class PParagraph(PTree):
    def __init__(self, subtree):
        self.it = subtree

    def debug(self):
        return ('Paragraph', self.it.debug())

    def isEmpty(self):
        return self.it.isEmpty()

class PHeading(PTree):
    def __init__(self, title, level):
        self.title = title
        self.level = level

    def debug(self):
        return ('Heading', self.level, self.title)

class PAuthor(PTree):
    def __init__(self, author):
        self.author = author

    def getAuthor(self):
        return self.author

    def debug(self):
        return ('Author', self.author)

class PDescription(PTree):
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def debug(self):
        return ('Description', self.key.debug(), self.value.debug())

class PItemize(PTree):
    def __init__(self, items):
        self.items = items

    def debug(self):
        return ('Itemize', [item.debug() for item in self.items])

class PItem(PTree):
    def __init__(self, subtree):
        self.it = subtree

    def debug(self):
        return ('Item', self.it.debug())

class Chargroup:
    """
    Abstract class where all char-groups inherit from.

    A char group is a group of sucessive characters within
    a line group, forming a logical unit within that line
    group, like an emphasis, or a math environment.
    """
    def __init__(self, initial=None):
        self.text = ''
        self.printname = 'abstract chargroup'
        if initial is not None:
            self.append(initial)

    def append(self, chars):
        """
        Append the given (possibly empty) sequence of chars to that group.
        """
        self.text = self.text + chars

    def debug(self):
        return (self.printname, self.text)

    def parse(self):
        return PLeaf(self.text)

    @classmethod
    def startshere(self, char, lookahead=None):
        """
        Return True, if a new chargroup of this type starts at the
        given char, which itself is followed by the lookahead.
        The lookahead is None, if the given char is the last char
        of the line group.
        """
        return False

    def enforcecontinuation(self, char):
        """
        Return True, if if this group insists in taking that next character,
        regardless of whether other groups might start here.
        """
        return False

    def rejectcontinuation(self, char):
        """
        Return True, if this group refuses to accept that next character, even
        if that means a new Simplegroup has to be started.
        """
        return False

class Simplegroup(Chargroup):
    """
    The default char group, without any special markup.
    """
    def __init__(self, initial=None):
        Chargroup.__init__(self, initial=initial)
        self.printname = 'simple chargroup'

class Emphgroup(Chargroup):
    """
    The group for _emphasized text_.
    """
    def __init__(self, initial=None):
        Chargroup.__init__(self, initial=initial)
        self.printname = 'emph group'

    @classmethod
    def startshere(self, char, lookahead=None):
        return char == '_'

    def rejectcontinuation(self, char):
        if len(self.text) < 2:
            return False
        return self.text[-1] == '_'

    def enforcecontinuation(self, char):
        ## Force to get the closing _
        if self.rejectcontinuation(char):
            return False
        return char == '_'

    def parse(self):
        return PEmph(self.text[1:-1])


def groupchars(text, supportedgroups):
    """
    Given a string (considered a list of chars) and a list of
    Chargroups to support, group the chars accordingly.
    """
    current = Simplegroup()
    groups = []
    for i in range(len(text)):
        c = text[i]
        if i + 1 < len(text):
            lookahead = text[i+1]
        else:
            lookahead = None

        if current.enforcecontinuation(c):
            current.append(c)
        else:
            handled = False
            for group in supportedgroups:
                if not handled:
                    if group.startshere(c, lookahead=lookahead):
                        groups.append(current)
                        current = group(c)
                        handled = True
            if not handled:
                if not current.rejectcontinuation(c):
                    current.append(c)
                else:
                    groups.append(current)
                    current = Simplegroup(c)
    groups.append(current)
    return groups
    

def defaultInnerParse(lines):
    features = [Simplegroup, Emphgroup]
    text = '\n'.join(lines)
    groups = groupchars(text, features)
    if len(groups) == 1:
        return groups[0].parse()
    else:
        return PSequence([g.parse() for g in groups])

class Linegroup:
    """
    Abstract class where all line-groups inherit from.

    A line group is a group of sucessive lines forming a logical
    unit, like a paragraph, an item in an enumeration, etc.

    Within a line group, further parsing is carried out for more
    fine granular markup, like emphazising words, math-mode, etc.

    Linegroups can then be grouped together, if desired. E.g. successive
    item-entries cann be grouped to an itemization environment, thus
    yielding a parse tree of the whole dokument.
    """
    def __init__(self, initialline=None):
        self.lines = []
        self.printname = "abstract linegroup"
        if initialline is not None:
            self.appendline(initialline)

    @classmethod
    def startshere(self, line, after=None):
        """
        Decide if this line starts a new group of the given type,
        assuming that it occurs after the group provided in in
        the optional argument.
        """
        return False

    def rejectcontinuation(self, lines):
        """
        Decide that this group definitely does not want any more lines,
        and, in the worst case, a new paragraph has to be started.
        """
        return False

    def enforcecontinuation(self, line):
        """
        Decide if this group enforces that the next line belongs to
        the current group, even though it could start a new group.
        Useful for ednotes or similar greedy groups.
        """
        return False

    def parse(self):
        """
        Return a representation of this linegroup as PTree.
        """
        return defaultInnerParse(self.lines)

    def appendline(self, line):
        self.lines.append(line)

    def debug(self):
        return (self.printname, self.lines)


class Paragraph(Linegroup):
    """
    A standard paragraph. This hopefully should be the most common
    line group in a document.
    """
    
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Paragraph"

    def appendline(self, line):
        if not isemptyline(line):
            Linegroup.appendline(self, line)

    @classmethod
    def startshere(self, line, after=None):
        return isemptyline(line)

    def parse(self):
        return PParagraph(defaultInnerParse(self.lines))

def isMirrorBracket(firstline, lastline):
    """
    Return True iff lastline ends with the matching
    bigbracket to the one the firstline starts with.
    """
    closing = { '{' : '}', '(' : ')', '<' : '>', '[' : ']' }

    left = firstline.split(' ')[0]
    right = lastline.rstrip().split(' ')[-1]

    if len(left) < 1:
        return False

    if len(left) != len(right):
        return False
    
    for i in range(len(left)):
        c = left[i]
        if c in closing:
            c = closing[c]
        if right[-1 - i] != c:
            return False

    return True

class Ednote(Linegroup):
    """
    Notes to the editor; also used to enter text without any changes or
    further parsing. May contain empty lines.
    """

    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Ednote"

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith('{')

    def enforcecontinuation(self, line):
        if len(self.lines) < 1:
            return True
        if isMirrorBracket(self.lines[0], self.lines[-1]):
           return False
        return not isMirrorBracket(self.lines[0], line)

    def rejectcontinuation(self, line):
        return not self.enforcecontinuation(line)

    def parse(self):
        ## first and last line contain the opening and closing brackets
        if len(self.lines) < 1:
            return PEdnote('\n'.join(self.lines))
        if len(self.lines) == 1:
            line = self.lines[0]
            splitline = line.split(' ')
            return PEdnote(' '.join(splitline[1:-1]))

        firstlinesplit = self.lines[0].split(' ', 1)
        if len(firstlinesplit) > 1:
            start = firstlinesplit[1] + '\n'
        else:
            start = ''
        lastlinesplit = self.lines[-1].rstrip().rsplit(' ', 1)
        if len(lastlinesplit) > 1:
            end = '\n' + lastlinesplit[0]
        else:
            end = ''
        return PEdnote(start + '\n'.join(self.lines[1:-1]) + end)


class Heading(Linegroup):
    """
    Headings, marked [As such] in dokuforge
    """
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Heading"

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith('[') and not line.startswith('[[')

    def getTitle(self):
        title = ' '.join(self.lines)
        while title.startswith('['):
            title = title[1:]
        while title.endswith(']'):
            title = title[:-1]
        return title

    def parse(self):
        return PHeading(self.getTitle(), 1)

class Subheading(Heading):
    """
    Subheadings, markes [[as such]] in dokuforge
    """
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "SubHeading"

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith('[[') and not line.startswith('[[[')

    def parse(self):
        return PHeading(self.getTitle(), 2)

class Author(Linegroup):
    """
    List of authors, marked (Some Author) in dokuforge
    """
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Author"
    
    @classmethod
    def startshere(self, line, after=None):
        return line.startswith('(') and isinstance(after, Heading)

    def parse(self):
        author = ' '.join(self.lines)
        while author.startswith('('):
            author = author[1:]
        while author.endswith(')'):
            author = author[:-1]
        return PAuthor(author)

class Item(Linegroup):
    """
    An entry of an itemization, marked as
    - first
    - second
    - third
    in Dokuforge.
    """
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Item"
    
    @classmethod
    def startshere(self, line, after=None):
        return line.startswith('- ')

    def parse(self):
        if len(self.lines) < 1:
            return PItem(defaultInnerParse(self.lines))
        firstline = self.lines[0]
        while firstline.startswith('-'):
            firstline = firstline[1:]
        while firstline.startswith(' '):
            firstline = firstline[1:]
        withcleanedfirstline = [firstline]
        withcleanedfirstline.extend(self.lines[1:])
        return PItem(defaultInnerParse(withcleanedfirstline))

class Description(Linegroup):
    """
    *Description* explain a word in a gloassary
    """
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Description"
    
    @classmethod
    def startshere(self, line, after=None):
        return line.startswith('*')

    def parse(self):
        if len(self.lines) < 1:
            return PLeaf('')
        firstline = self.lines[0]
        while firstline.startswith('*'):
            firstline = firstline[1:]
        keyrest = firstline.split('*')
        key = keyrest[0]
        if len(keyrest) > 1:
            rest = keyrest[1] + '\n'
        else:
            rest = ''
        body = rest + '\n'.join(self.lines[1:])
        return PDescription(defaultInnerParse([key.strip()]),
                            defaultInnerParse([body.strip()]));

def grouplines(lines, supportedgroups):
    """
    Given a list of lines and a list of Linegroup to support, group
    lines accordingly.

    The grouping is done based on the startshere, enforcecontinuatuion,
    and rejectcontinuation methods provided by the supported linegroups.
    """
    current = Paragraph()
    groups = []
    for line in lines:
        if current.enforcecontinuation(line):
            current.appendline(line)
        else:
            handled = False
            for linegroup in supportedgroups:
                if not handled:
                    if linegroup.startshere(line, after=current):
                        groups.append(current)
                        current = linegroup(initialline=line)
                        handled = True
            if not handled:
                if not current.rejectcontinuation(line):
                    current.appendline(line)
                else:
                    groups.append(current)
                    current = Paragraph(line)
    groups.append(current)
    return groups

def removeEmpty(ptrees):
    """
    Given a list of PTrees, return a list containing the
    same elements but the empty ones.
    """
    result = []
    for ptree in ptrees:
        if not ptree.isEmpty():
            result.append(ptree)
    return result

def groupItems(ptrees):
    """
    For a given list of PTrees, return the same list, but
    with every sequence of PItems replaced by an PItemize.
    """
    result = []
    pos = 0
    while pos < len(ptrees):
        if isinstance(ptrees[pos], PItem):
            i = pos
            while i < len(ptrees) and isinstance(ptrees[i], PItem):
                i += 1
            result.append(PItemize(ptrees[pos:i]))
            pos = i
        else:
            result.append(ptrees[pos])
            pos += 1
    return result


def dfLineGroupParser(text):
    features = [Paragraph, Heading, Author, Subheading, Item, Description, Ednote]
    groups = grouplines(text.splitlines(), features)
    ptrees = [g.parse() for g in groups]
    ptrees = groupItems(ptrees)
    ptrees = removeEmpty(ptrees)
    return PSequence(ptrees)

if __name__ == "__main__":
    example = """
[Ueberschrift]
(Autor)

Hier ist ein
Paragrpah ueber 3
Zeilen.

[[Unterueberschrift]]
(Autor)

Und ein weiterer
Absatz.
(Man beachte, dass diese Klammer
keine Autorenangabe beinhaltet)

{ Ednote: short }

{ Ednote:

  Mit Leerzeile! }

{((

Fancy Ednote, containing Code

for(i=0, i< 10; i++) {
  printf("%d\n", i);
}

))}
  
{ Ednote }
Hier sollte eigentlich ein neuer Absatz beginnen.

Und nun noch eine Aufzaehlung.
- erstens
- zweitens
- drittens

Und ein weiterer Absatz.
Dieser enthaelt _betonten_ Text.

*Modularitaet* ist die Wesentliche Idee hinter
diesem Ansatz der Groupierung von Zeilen.

*Flexibilitaet fuer Erweiterungen* ist etwas,
worauf wir wohl nicht verzichten koennen.

Text text...
{ sehr kurze, eingebunde ednote }
Noch ein neuer Absatz.
"""
    print dfLineGroupParser(example).debug()
