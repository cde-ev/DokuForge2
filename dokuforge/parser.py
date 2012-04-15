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

def defaultInnerParse(lines):
    return PLeaf('\n'.join(lines))

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

    def startshere(self, line, after=None):
        """
        Decide if this line starts a new group of the given type,
        assuming that it occurs after the group provided in in
        the optional argument.
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

    def startshere(self, line, after=None):
        return isemptyline(line)

    def parse(self):
        return PParagraph(defaultInnerParse(self.lines))

class Heading(Linegroup):
    """
    Headings, marked [As such] in dokuforge
    """
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Heading"

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

    The grouping is done based on the startshere and enforcecontinuatuion
    functions provided by the supported linegroups.
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
                        current = linegroup.__class__(initialline=line)
                        handled = True
            if not handled:
                current.appendline(line)
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
    features = [Paragraph(), Heading(), Author(), Subheading(), Item(), Description()]
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

Und nun noch eine Aufzaehlung.
- erstens
- zweitens
- drittens

Und ein weiterer Absatz.

*Modularitaet* ist die Wesentliche Idee hinter
diesem Ansatz der Groupierung von Zeilen.

*Flexibilitaet fuer Erweiterungen* ist etwas,
worauf wir wohl nicht verzichten koennen.
"""
    print dfLineGroupParser(example).debug()
