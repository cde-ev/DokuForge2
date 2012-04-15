import re

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

    def appendline(self, line):
        self.lines.append(line)

    def debug(self):
        return (self.printname, self.lines)


def isemptyline(line):
    return re.match('^[ \t]*$', line)

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

class Heading(Linegroup):
    """
    Headings, marked [As such] in dokuforge
    """
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Heading"

    def startshere(self, line, after=None):
        return line.startswith('[') and not line.startswith('[[')

class Author(Linegroup):
    """
    List of authors, marked (Some Author) in dokuforge
    """
    def __init__(self, initialline=None):
        Linegroup.__init__(self, initialline=initialline)
        self.printname = "Author"
    
    def startshere(self, line, after=None):
        return line.startswith('(') and after.__class__==Heading


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


if __name__ == "__main__":
    example = """
[Ueberschrift]
(Autor)

Hier ist ein
Paragrpah ueber 3
Zeilen.

Und ein weiterer
Absatz.
(Man beachte, dass diese Klammer
keine Autorenangabe beinhaltet)
"""
    features = [Paragraph(), Heading(), Author()]
    groups = grouplines(example.splitlines(), features)
    print [g.debug() for g in groups]
