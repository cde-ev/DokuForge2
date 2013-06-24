# -*- coding: utf-8 -*-
import collections
import functools
import itertools
import textwrap
import math
import re


## How To Read This File?
##
## Everything is sorted in dependency order, but the
## best way to understand the parsing concept is as follows.
##
## 1. Look at the abstract class Linegroup, then the functions
##    grouplines and dfLineGroupParser, and then at the
##    decendents of Linegroup. This is the outer parser.
##
## 2. Look at the abstract class Chargroup, then the functions
##    groupchars and defaultInnerParser, and then at the decendents
##    of Chargroup. This is the inner parser.
##
## 3. Now might be a good time, to read PTree and its decendents.
##
## For normal parsing, that's it.
##
## 4. If you're also interested in the micotypography for the TeX
##    export, the story is as follows. A microtype feature is a
##    function str -> [str] taking a textual unit and returning
##    a list of textual units after the feature is applied, splitting
##    the original unit where approprate. A microtype is given
##    by a list of features and has the semantics of sucessively
##    applying these features (in the sense of the list monad), and
##    finally concatenating the obtained tokens. In other words, the
##    seamantics is given by
##    \w -> ((foldl (>>=) (return w) features) >>= id)

class Estimate(collections.namedtuple("Estimate",
            "chars ednotechars weightedchars blobs")):
    """
    @type chars: int
    @type ednotechars: int
    @type weightedchars: float
    @type blobs: int
    """
    # The following constants must be float in Py2.X to avoid int division.
    charsperpage = 3000.0
    charsperline = 80.0
    blobsperpage = 3.0

    @classmethod
    def fromText(cls, s):
        n = len(s)
        return cls(n, 0, n, 0)

    @classmethod
    def fromParagraph(cls, s):
        return cls.fromText(s).fullline()

    @classmethod
    def fromTitle(cls, s):
        n = len(s)
        wc = math.ceil(n / cls.charsperline) * cls.charsperline * 2
        return cls(n, 0, wc, 0)

    @classmethod
    def fromEdnote(cls, s):
        return cls(0, len(s), 0, 0)

    @classmethod
    def fromBlobs(cls, blobs):
        return cls(0, 0, 0, len(blobs))

    @classmethod
    def fromNothing(cls):
        return cls(0, 0, 0, 0)

    @classmethod
    def emptyLines(cls, linecount=1):
        return cls(0, 0, cls.charsperline * linecount, 0)

    @property
    def pages(self):
        return self.weightedchars / self.charsperpage

    @property
    def ednotepages(self):
        return self.ednotechars / self.charsperpage

    @property
    def blobpages(self):
        return self.blobs / self.blobsperpage

    def fullline(self):
        weightedchars = math.ceil(self.weightedchars / self.charsperline) \
                * self.charsperline
        return Estimate(self.chars, self.ednotechars, weightedchars, self.blobs)

    def __add__(self, other):
        return Estimate(*[a + b for a, b in zip(self, other)])

    def __mul__(self, num):
        return Estimate(*[num * field for field in self])

    __rmul__ = __mul__


def intersperse(iterable, delimiter):
    it = iter(iterable)
    for x in it:
        yield x
        break
    for x in it:
        yield delimiter
        yield x

class Escaper:
    def __init__(self, sequence, escaped):
        self.sequence = sequence
        self.escaped = escaped

    def __call__(self, word):
        return intersperse(word.split(self.sequence), self.escaped)

def acronym(word):
    """
    All-capital words should be displayed in smaller font.
    But don't mangle things like 'T-Shirt' or 'E-Mail'.
    """
    if len(word) > 1 and word.isalpha() and word.isupper():
        word = u'\\acronym{%s}' % word
    yield word

def  standardAbbreviations(word):
    """
    Do spacing for standard abbreviations.
    """
    abb = { 
    # FIXME we want '~\dots{}' in nearly every case
        u'...': u'\\dots{}',
        u'bzw.': u'bzw.',
        u'ca.': u'ca.',
        u'd.h.': u'd.\\,h.',
        u'etc.': u'etc.',
        u'f.': u'f.',
        u'ff.': u'ff.',
        u'n.Chr.': u'n.\\,Chr.',
        u'o.Ä.': u'o.\\,Ä.',
        u's.o.': u's.\\,o.',
        u'sog.': u'sog.',
        u's.u.': u's.\\,u.',
        u'u.a.': u'u.\\,a.',
        u'v.Chr.': u'v.\\,Chr.',
        u'vgl.': u'vgl.',
        u'z.B.': u'z.\\,B.'}

    yield abb.get(word, word)

splitEllipsis = Escaper(u"...", u"...")
# Replace the ellipsis symbol ... by \dots

def naturalNumbers(word):
    """
    Special Spacing for numbers.
    """
    # FIXME negative numbers only work because '-' currently is a separator
    # FIXME we want some special spacing around numbers:
    #       - a number followed by a dot wants a thin space: '21.\,regiment'
    #       - a number followed by a unit wants a thin space: 'weight 67\,kg'
    #       - a number followed by a percent sign wants a thin space: '51\,\%'
    if not word.isdigit():
        yield word
    else:
        value = int(word)
        if value < 10000:
            # no special typesetting for 4 digits only
            yield u"%d" % value
        else:
            result = u''
            while value >= 1000:
                threedigits = value % 1000
                result = u'\\,%03d%s' % (threedigits, result)
                value = value // 1000
            yield u'%d%s' % (value, result)

def openQuotationMark(word):
    if len(word) > 1 and word.startswith(u'"'):
        yield u'"`'
        word = word[1:]
    yield word

def closeQuotationMark(word):
    if len(word) > 1 and word.endswith(u'"'):
        yield word[:-1]
        yield u'"\''
    else:
        yield word

def fullStop(word):
    if len(word) > 1 and word.endswith(u'.'):
        yield word[:-1]
        yield u'.'
    else:
        yield word

percent = Escaper(u"%", ur"\%")

ampersand = Escaper(u"&", ur"\&")

hashmark = Escaper(u"#", ur"\#")

caret = Escaper(u"^", ur"\caret{}")

quote = Escaper(u"'", u"'")

class EscapeCommands:
    """
    Mark all controll sequence tokens as forbidden, except
    a list of known good commands.
    """
    escapechar = u"\\"
    allowed = set(u"\\" + symbol for symbol in [
    # produced by our own microtypography or otherwise essential
    u' ', u',', u'%', u'dots', u'\\', u'"', u'acronym', u'&',
    u'#', u'caret',
    # other allowed commands; FIXME: complete and put to a separate file
    ## list of useful math commands mostly taken
    ## from 'A Guide To LaTeX' by Kopka
    ## greek letters
    u'alpha', u'beta', u'gamma', u'delta', u'epsilon', u'zeta',
    u'eta', u'theta', u'iota', u'kappa', u'lambda', u'mu',
    u'nu', u'xi', u'pi', u'rho', u'sigma', u'tau', u'upsilon',
    u'phi', u'chi', u'psi', u'omega', u'Gamma', u'Delta',
    u'Theta', u'Lambda', u'Xi', u'Pi', u'Sigma', u'Phi', u'Psi',
    u'Omega', u'varepsilon', u'vartheta', u'varpi', u'varrho',
    u'varsigma', u'varphi',
    ## math layout
    u'frac', u'sqrt', u'sum', u'int', u'ldots', u'cdots',
    u'vdots', u'ddots', u'oint', u'prod', u'coprod'
    ## math symbols
    u'pm', u'cap', u'circ', u'bigcirc' u'mp', u'cup', u'bullet',
    u'Box' u'times', u'uplus', u'diamond', u'Diamond', u'div',
    u'sqcap', u'bigtriangleup', u'cdot', u'sqcup',
    u'bigtriangledown', u'ast', u'vee', u'unlhd', u'triangleleft',
    u'star', u'wedge', u'unrhd', u'triangleright', u'dagger',
    u'oplus', u'oslash', u'setminus', u'ddagger', u'ominus',
    u'odot', u'wr', u'amalg', u'otimes',
    ## math relations
    u'le', u'leq', u'ge', u'geq', u'neq', u'sim', u'll', u'gg',
    u'doteq', u'simeq', u'subset', u'supset', u'approx', u'asymp',
    u'subseteq', u'supseteq', u'cong', u'smile', u'sqsubset',
    u'sqsupset', u'equiv', u'frown', u'sqsubseteq', u'sqsupseteq',
    u'propto', u'bowtie', u'in', u'ni', u'prec', u'succ',
    u'vdash', u'dashv', u'preceq', u'succeq', u'models', u'perp',
    u'parallel', u'mid',
    ## negations
    u'not', u'notin',
    ## arrows
    u'leftarrow', u'gets', u'longleftarrow', u'uparrow',
    u'Leftarrow', u'Longleftarrow', u'Uparrow', u'rightarrow',
    u'to', u'longrightarrow', u'downarrow', u'Rightarrow',
    u'Longrightarrow', u'Downarrow', u'leftrightarrow',
    u'longleftrightarrow', u'updownarrow', u'Leftrightarrow',
    u'Longleftrightarrow', u'Updownarrow', u'mapsto', u'longmapsto',
    u'nearrow', u'hookleftarrow', u'hookrightarrow', u'searrow',
    u'leftharpoonup', u'rightharpoonup', u'swarrow',
    u'leftharpoondown', u'rightharpoondown', u'nwarrow',
    u'rightleftharpoons', u'leadsto',
    ## various symbols
    u'aleph', u'prime', u'forall', u'hbar', u'emptyset',
    u'exists', u'imath', u'nablaa', u'neg', u'triangle', u'jmath',
    u'surd', u'flat', u'clubsuit', u'ell', u'partial', u'natural',
    u'diamondsuit', u'wp', u'top', u'sharp', u'heartsuit', u'Re',
    u'bot', u'spadesuit', u'Im', u'vdash', u'angle', u'Join',
    u'mho', u'dashv', u'backslash', u'infty',
    ## big symbols
    u'bigcap', u'bigodot', u'bigcup', u'bigotimes', u'bigsqcup',
    u'bigoplus', u'bigvee', u'biguplus', u'bigwedge',
    ## function names
    u'arccos', u'cosh', u'det', u'inf' u'limsup', u'Pr', u'tan',
    u'arcsin', u'cot', u'dim', u'ker', u'ln', u'sec', u'tanh',
    u'arctan', u'coth', u'exp', u'lg', u'log', u'sin', u'arg',
    u'csc', u'gcd', u'lim', u'max', u'sinh', u'cos', u'deg',
    u'hom', u'liminf', u'min', u'sup',
    ## accents
    u'hat', u'breve', u'grave', u'bar', u'check', u'acute',
    u'ti1de', u'vec', u'dot', u'ddot', u'mathring',
    ## parens
    u'left', u'right', u'lfloor', u'rfloor', u'lceil', u'rceil',
    u'langle', u'rangle',
    ## misc
    u'stackrel', u'binom', u'mathbb'
    # FIXME think about including environments, these can come up in complex
    # mathematical formulas, but they could also be abused (more in the "we
    # don't want users to make typesetting decisions" style of misuse, than
    # anything critical).
    # ## environments
    # u'begin', u'end',
    ])

    command_re = re.compile("(%s(?:[a-zA-Z]+|.))" % re.escape(escapechar))

    def forbid(self, word):
        return u'\\forbidden' + word

    def __call__(self, word):
        for part in self.command_re.split(word):
            if part.startswith(self.escapechar):
                if part in self.allowed:
                    yield part
                elif part == self.escapechar:
                    # Oh, a backslash at end of input;
                    # maybe we broke into words incorrectly,
                    # so just return something safe.
                    yield '\\@\\ '
                else:
                    yield self.forbid(part)
            else:
                yield part

escapeCommands = EscapeCommands()

escapeEndEdnote = Escaper(ur"\end{ednote}", u"|end{ednote}")
# Escpage the string \\end{ednote}, so that ednotes end
# where we expect them to end.

class SplitSeparators:
    def __init__(self, separators):
        self.splitre = re.compile("([%s])" % re.escape(separators))

    def __call__(self, word):
        return self.splitre.split(word)

def applyMicrotypefeatures(wordlist, featurelist):
    """
    sequentially apply (in the sense wordlist >>= feature)
    the features to the wordlist. Return the concatenation
    of the result.
    @type wordlist: [unicode]
    """
    for feature in featurelist:
        wordlistlist = []
        for word in wordlist:
            assert isinstance(word, unicode)
            wordlistlist.append(feature(word))
        wordlist = itertools.chain(*wordlistlist)
    return ''.join(wordlist)

def defaultMicrotype(text):
    """
    @type text: unicode
    """
    assert isinstance(text, unicode)
    # FIXME '-' should not be a separator so we are able to detect dashes '--'
    #       however this will break NaturalNumbers for negative inputs
    separators = ' \t,;()-' # no point, might be in abbreviations
    features = [SplitSeparators(separators),
                splitEllipsis, percent, ampersand, caret, hashmark, quote,
                standardAbbreviations, fullStop, openQuotationMark,
                closeQuotationMark, acronym, naturalNumbers, escapeCommands]
    return applyMicrotypefeatures([text], features)

def mathMicrotype(text):
    # FIXME we want to substitute '...' -> '\dots{}' in math mode too
    features = [percent, hashmark, naturalNumbers, escapeCommands]
    return applyMicrotypefeatures([text], features)

def ednoteMicrotype(text):
    return applyMicrotypefeatures([text], [escapeEndEdnote])

def isemptyline(line):
    return re.match('^[ \t]*$', line)

def wrap(text, subsequent_indent=''):
    """
    Wraps text to width 70.
    """
    # triple @ to label linebreaks after long lines before wrapping
    text = re.sub("([^\n]{160})\n", "\\1\\@\\@\\@\n", text)
    return textwrap.fill(text, subsequent_indent=subsequent_indent,
            drop_whitespace = True, replace_whitespace = True,
            break_long_words = False, break_on_hyphens = False)

class PTree:
    """
    Abstract class where all parsed objects inherit from.
    """
    def debug(self):
        return None

    def isEmpty(self):
        return False

    def toTex(self):
        """
        return a tex-representation of the parsed object.
        """
        raise NotImplementedError

    def toHtml(self):
        """
        return a html-representation of the parsed object.
        """
        raise NotImplementedError

    def toDF(self):
        """
        return a canonical representation of the text in
        dokuforge markup language.
        """
        raise NotImplementedError

    def toEstimate(self):
        """
        @rtype: Estimate
        """
        raise NotImplementedError

class PSequence(PTree):
    """
    A piece of text formed by juxtaposition of several
    Parse Trees (usually paragraphs).
    """
    def __init__(self, parts):
        self.parts = parts

    def debug(self):
        return ('Sequence', [part.debug() for part in self.parts])

    def toTex(self):
        result = ''
        for part in self.parts:
            result = result + part.toTex()
        return result

    def toHtml(self):
        result = ''
        for part in self.parts:
            result = result + part.toHtml()
        return result

    def toDF(self):
        result = ''
        for part in self.parts:
            result = result + part.toDF()
        return result

    def toEstimate(self):
        return functools.reduce(lambda a, b: a + b,
                      (part.toEstimate() for part in self.parts),
                      Estimate.fromNothing())

class PLeaf(PTree):
    """
    A piece of text that contains no further substructure.
    """
    def __init__(self, text):
        assert isinstance(text, unicode)
        self.text = text

    def debug(self):
        return self.text

    def isEmpty(self):
        return isemptyline(self.text)

    def toTex(self):
        return defaultMicrotype(self.text)

    def toHtml(self):
        result = self.text
        result = result.replace(u'&', u'&amp;')
        result = result.replace(u'<', u'&lt;')
        result = result.replace(u'>', u'&gt;')
        result = result.replace(u'"', u'&#34;')
        result = result.replace(u"'", u'&#39;')
        return result

    def toDF(self):
        return self.text

    def toEstimate(self):
        return Estimate.fromText(self.text)

class PEmph(PTree):
    """
    An emphasized piece of text.
    """
    def __init__(self, text):
        self.text = PLeaf(text)

    def debug(self):
        return ('emph', self.text.text)

    def toTex(self):
        return '\\emph{%s}' % self.text.toTex()

    def toHtml(self):
        return '<em>%s</em>' % self.text.toHtml()

    def toDF(self):
        return u'_%s_' % self.text.toDF()

    def toEstimate(self):
        return self.text.toEstimate()

class PMath(PTree):
    """
    An non-display math area.
    """
    def __init__(self, text):
        self.text = PLeaf(text)

    def debug(self):
        return ('math', self.text)

    def toTex(self):
        return u'$%1s$' % mathMicrotype(self.text.text)

    def toHtml(self):
        return '$%1s$' % self.text.toHtml()

    def toDF(self):
        return u'$%1s$' % self.text.toDF()

    def toEstimate(self):
        return self.text.toEstimate()

class PDisplayMath(PTree):
    """
    An display math area.
    """
    def __init__(self, text):
        self.text = PLeaf(text)

    def debug(self):
        return ('displaymath', self.text.text)

    def toTex(self):
        return '$$%1s$$' % mathMicrotype(self.text.text)

    def toHtml(self):
        return "<div class=\"displaymath\">$$%1s$$</div>" % self.text.toHtml()

    def toDF(self):
        return u'$$%1s$$' % self.text.toDF()

    def toEstimate(self):
        return Estimate.fromText(self.text.text).fullline() + \
                Estimate.emptyLines(2)

class PEdnote(PTree):
    """
    An Ednote; contents are compeletly unchanged.
    """
    def __init__(self, text):
        self.text = PLeaf(text)

    def isEmpty(self):
        # the mere fact that there was an Ednote
        # is already worth mentioning
        return False

    def debug(self):
        return ('Ednote', self.text.text)

    def toTex(self):
        return u'\n\\begin{ednote}\n%s\n\\end{ednote}\n' % \
                ednoteMicrotype(self.text.text)

    def toHtml(self):
        return '\n<pre class="ednote">\n%s\n</pre>\n' % self.text.toHtml()

    def toDF(self):
        # find a bracket combination not in the text
        text = self.text.toDF()
        n = 1
        while text.find(u'}' * n) >= 0:
            n += 1
        return u'\n%s\n%s\n%s\n' % (u'{' * n, text, u'}' * n)

    def toEstimate(self):
        return Estimate.fromEdnote(self.text.text)

class PParagraph(PTree):
    def __init__(self, subtree):
        self.it = subtree

    def debug(self):
        return ('Paragraph', self.it.debug())

    def isEmpty(self):
        return self.it.isEmpty()

    def toTex(self):
        return u'\n%s\n' % wrap(self.it.toTex())

    def toHtml(self):
        return '\n<p>\n'  + self.it.toHtml() + '\n</p>\n'

    def toDF(self):
        return u'\n\n%s\n' % self.it.toDF()

    def toEstimate(self):
        return self.it.toEstimate().fullline()

class PHeading(PTree):
    def __init__(self, title, level):
        self.title = PLeaf(title)
        self.level = level

    def debug(self):
        return ('Heading', self.level, self.getTitle())

    def toTex(self):
        return '\n\\%ssection{%s}\n' % ("sub" * self.level, self.title.toTex())

    def toHtml(self):
        n = self.level + 1
        return u'\n<h%d>%s</h%d>\n' % (n, self.title.toHtml(), n)

    def toDF(self):
        n = self.level + 1
        return u'\n\n%s%s%s' % (u'[' * n, self.title.toDF(), u']' * n)

    def getLevel(self):
        return self.level

    def getTitle(self):
        return self.title.text

    def toEstimate(self):
        return Estimate.fromTitle(self.getTitle())

class PAuthor(PTree):
    def __init__(self, author):
        self.author = PLeaf(author)

    def getAuthor(self):
        return self.author.text

    def debug(self):
        return ('Author', self.getAuthor())

    def toTex(self):
        return '\\authors{%s}\n' % self.author.toTex()

    def toHtml(self):
        return u'<i>%s</i>' % self.author.toHtml()

    def toDF(self):
        return u'\n(%s)' % self.author.toDF()

    def toEstimate(self):
        return Estimate.fromParagraph(self.getAuthor())

class PDescription(PTree):
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def debug(self):
        return ('Description', self.key.debug(), self.value.debug())

    def toTex(self):
        return '\n' + wrap('\\paragraph{' + self.key.toTex() + '} ' + self.value.toTex()) + '\n'

    def toHtml(self):
        return '\n<p><b>' + self.key.toHtml() + '</b> ' + self.value.toHtml() + '\n</p>\n'

    def toDF(self):
        return u'\n\n*%1s* %s' % (self.key.toDF(), self.value.toDF())

    def toEstimate(self):
        return self.key.toEstimate() + self.value.toEstimate()

class PItemize(PTree):
    def __init__(self, items):
        self.items = items
        self.isEnum = False
        if len(self.items) > 0:
            self.isEnum = self.items[0].isEnumerate()

    def debug(self):
        return ('Itemize', [item.debug() for item in self.items])

    def isEnumerate(self):
        return self.isEnum

    def toTex(self):
        itemtype =  'itemize'
        if self.isEnumerate():
            itemtype = 'enumerate'
        result = '\n\\begin{%s}' % itemtype
        for item in self.items:
            result = result + item.toTex()
        result = result + ('\n\\end{%s}\n' % itemtype)
        return result

    def toHtml(self):
        itemtype =  'ul'
        if self.isEnumerate():
            itemtype = 'ol'
        result = '\n<%s>' % itemtype
        for item in self.items:
            result = result + item.toHtml()
        result = result + ('\n</%s>\n' % itemtype)
        return result

    def toDF(self):
        return u"\n" + u"".join(item.toDF() for item in self.items)

    def toEstimate(self):
        return functools.reduce(lambda a, b: a + b + Estimate.emptyLines(0.5),
                      [item.toEstimate() for item in self.items],
                      Estimate.fromNothing()) + \
                Estimate.emptyLines(2)

class PItem(PTree):
    def __init__(self, subtree, number=None):
        self.it = subtree
        self.number=number

    def debug(self):
        return ('Item', self.it.debug(), self.number)

    def isEnumerate(self):
        return self.number is not None

    def toTex(self):
        if self.number is None:
            return '\n' + wrap('\\item ' + self.it.toTex(), subsequent_indent='  ')
        else:
            return '\n% ' + self.number + '\n' + wrap('\\item ' + self.it.toTex(), subsequent_indent='  ')

    def toHtml(self):
        return '\n<li> ' + self.it.toHtml()

    def toDF(self):
        if self.number is None:
            return u'\n-' + self.it.toDF()
        else:
            return u'\n%s. %s' % (self.number, self.it.toDF())

    def toEstimate(self):
        return self.it.toEstimate()

class Chargroup:
    """
    Abstract class where all char-groups inherit from.

    A char group is a group of sucessive characters within
    a line group, forming a logical unit within that line
    group, like an emphasis, or a math environment.
    """
    def __init__(self, initial=None):
        self.text = u''
        if initial is not None:
            self.append(initial)

    def append(self, chars):
        """
        Append the given (possibly empty) sequence of chars to that group.
        """
        self.text = self.text + chars

    def debug(self):
        return (self.__class__.__name__, self.text)

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

class Emphgroup(Chargroup):
    """
    The group for _emphasized text_.
    """
    def __init__(self, initial=None):
        Chargroup.__init__(self, initial=initial)

    @classmethod
    def startshere(self, char, lookahead=None):
        return char == u'_'

    def rejectcontinuation(self, char):
        if len(self.text) < 2:
            return False
        return self.text.endswith(u'_')

    def enforcecontinuation(self, char):
        ## Force to get the closing _
        if self.rejectcontinuation(char):
            return False
        return char == u'_'

    def parse(self):
        assert self.text.startswith(u"_")
        if self.text.endswith(u"_"):
            return PEmph(self.text[1:-1])
        else:
            return PEmph(self.text[1:])

class Mathgroup(Chargroup):
    """
    The group for simple (non dislay) math,
    like $a^2 + b^2$.
    """
    def __init__(self, initial=None):
        self.trailingbackslashs = 0
        self.done = False
        self.count = 0
        Chargroup.__init__(self, initial=initial)

    @classmethod
    def startshere(self, char, lookahead=None):
        return char == u'$' and lookahead != u'$'

    def append(self, chars):
        for c in chars:
            self.text = self.text + c
            self.count = self.count + 1
            if c == u'$' and self.count > 2:
                if self.trailingbackslashs % 2 == 0:
                    self.done = True

            if c == u'\\':
                self.trailingbackslashs = self.trailingbackslashs + 1
            else:
                self.trailingbackslashs = 0

    def enforcecontinuation(self, char):
        return not self.done

    def rejectcontinuation(self, char):
        return self.done

    def parse(self):
        result = self.text
        if result.startswith(u'$'):
            result = result[1:]
        if result.endswith(u'$'):
            result = result[:-1]
        return PMath(result)


class DisplayMathGroup(Chargroup):
    """
    The group for display math
    like $$ a^2 + b^2 = c^2$$
    """
    def __init__(self, initial=None):
        self.done = False
        self.trailingbackslashs = 0
        self.trailingdollar = 0
        self.count = 0
        Chargroup.__init__(self, initial=initial)

    @classmethod
    def startshere(self, char, lookahead=None):
        return char == u'$' and lookahead == u'$'

    def append(self, chars):
        for c in chars:
            self.text = self.text + c
            self.count = self.count + 1
            if c == u'$' and self.count > 2:
                if self.trailingdollar == 1:
                    self.done = True
                elif self.trailingbackslashs % 2 == 0:
                    self.trailingbackslashs=0
                    self.trailingdollar += 1
                else:
                    self.trailingbackslashs = 0
                    self.trailingdollar = 0
            elif c == u'\\':
                self.trailingdollar = 0
                self.trailingbackslashs += 1
            else:
                self.trailingdollar = 0
                self.trailingbackslashs = 0

    def enforcecontinuation(self, char):
        return not self.done

    def rejectcontinuation(self, char):
        return self.done

    def parse(self):
        result = self.text
        if result.startswith(u'$$'):
            result = result[2:]
        if result.endswith(u'$$'):
            result = result[:-2]
        if result.endswith(u'$'):
            result += u' '
        return PDisplayMath(result)


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
    """
    @type lines: [unicode]
    """
    features = [Simplegroup, Emphgroup, Mathgroup, DisplayMathGroup]
    text = u'\n'.join(lines)
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
    def __init__(self):
        self.lines = []

    @classmethod
    def startshere(self, line, after=None):
        """
        Decide if this line starts a new group of the given type,
        assuming that it occurs after the group provided in in
        the optional argument.
        """
        return False

    def rejectcontinuation(self, line):
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
        return (self.__class__.__name__, self.lines)


class Paragraph(Linegroup):
    """
    A standard paragraph. This hopefully should be the most common
    line group in a document.
    """
    def __init__(self):
        Linegroup.__init__(self)

    def appendline(self, line):
        if not isemptyline(line):
            Linegroup.appendline(self, line)

    @classmethod
    def startshere(self, line, after=None):
        return isemptyline(line)

    def parse(self):
        return PParagraph(defaultInnerParse(self.lines))

def splitleftbracket(line):
    openings = set([u'(', u'[', u'{'])
    bracket, rest = '', ''
    stillbracket = True
    for i in range(len(line)):
        c = line[i]
        if c not in openings:
            stillbracket = False
        if stillbracket:
            bracket = bracket + c
        else:
            rest = rest + c
    return [bracket, rest]

def splitrightbracket(line):
    line = line.rstrip()
    closings = set([u')', u']', u'}'])
    bracket, rest = u'', u''
    stillbracket = True
    for i in range(len(line)):
        c = line[len(line)-i-1]
        if c not in closings:
            stillbracket = False
        if stillbracket:
            bracket = c + bracket
        else:
            rest = c + rest
    return [rest, bracket]


def isMirrorBracket(firstline, lastline):
    """
    Return True iff lastline ends with the matching
    bigbracket to the one the firstline starts with.
    """
    closing = { u'{' : u'}', u'(' : u')', u'<' : u'>', u'[' : u']' }

    left = splitleftbracket(firstline)[0]
    right = splitrightbracket(lastline)[-1]

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
    def __init__(self):
        Linegroup.__init__(self)

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith(u'{')

    def enforcecontinuation(self, line):
        if len(self.lines) < 1:
            return True
        if isMirrorBracket(self.lines[0], self.lines[-1]):
           return False
        return True

    def rejectcontinuation(self, line):
        return not self.enforcecontinuation(line)

    def parse(self):
        ## first and last line contain the opening and closing brackets
        if len(self.lines) < 1:
            return PEdnote('\n'.join(self.lines))
        if len(self.lines) == 1:
            line = self.lines[0]
            withoutleftbracket = splitleftbracket(line)[1]
            withoutbracket = splitrightbracket(withoutleftbracket)[0]
            return PEdnote(withoutbracket)

        start = splitleftbracket(self.lines[0])[1]
        if len(start) > 0:
            start += u'\n'
        end = splitrightbracket(self.lines[-1])[0]

        if len(self.lines) > 2 and len(end) != 0:
            end = u'\n' + end

        return PEdnote(start + u'\n'.join(self.lines[1:-1]) + end)


class Heading(Linegroup):
    """
    Headings, marked [As such] in dokuforge
    """
    def __init__(self):
        Linegroup.__init__(self)

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith(u'[') and not line.startswith(u'[[')

    def enforcecontinuation(self, line):
        if isemptyline(line):
            return False
        if len(self.lines) < 1:
            return True
        return u']' not in set(self.lines[-1])

    def rejectcontinuation(self, line):
        return not self.enforcecontinuation(line)

    def getTitle(self):
        title = u' '.join(self.lines)
        title = title.lstrip(u'[')
        title = title.rstrip(u' \t')
        title = title.rstrip(u']')
        return title

    def parse(self):
        return PHeading(self.getTitle(), 0)

class Subheading(Heading):
    """
    Subheadings, markes [[as such]] in dokuforge
    """
    def __init__(self):
        Heading.__init__(self)

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith(u'[[') and not line.startswith(u'[[[')

    def parse(self):
        return PHeading(self.getTitle(), 1)

class Author(Linegroup):
    """
    List of authors, marked (Some Author) in dokuforge
    """
    def __init__(self):
        Linegroup.__init__(self)

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith(u'(') and isinstance(after, Heading)

    def enforcecontinuation(self, line):
        if isemptyline(line):
            return False
        if len(self.lines) < 1:
            return True
        return u')' not in set(self.lines[-1])

    def rejectcontinuation(self, line):
        return not self.enforcecontinuation(line)

    def parse(self):
        author = u' '.join(self.lines)
        author = author.lstrip(u'(')
        author = author.rstrip(u' \t')
        author = author.rstrip(u')')
        return PAuthor(author)

class Item(Linegroup):
    """
    An entry of an itemization, marked as
    - first
    - second
    - third
    in Dokuforge.
    """
    def __init__(self):
        Linegroup.__init__(self)

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith(u'- ')

    def parse(self):
        if len(self.lines) < 1:
            return PItem(defaultInnerParse(self.lines))
        firstline = self.lines[0]
        if firstline.startswith(u'-'):
            firstline = firstline[1:]
        withcleanedfirstline = [firstline]
        withcleanedfirstline.extend(self.lines[1:])
        return PItem(defaultInnerParse(withcleanedfirstline))

class EnumerateItem(Linegroup):
    """
    An entry in an enumeration, marked as
    1. First
    2. Second
    3. and so on
    in Dokuforge
    """
    def __init__(self):
        Linegroup.__init__(self)

    @classmethod
    def startshere(self, line, after=None):
        return re.match('^[0-9]+\.[ \t]', line)

    def parse(self):
        if len(self.lines) < 1:
            return PItem(defaultInnerParse(self.lines), number="1")
        firstline = self.lines[0]
        number = "1"
        m = re.match('^([0-9]+)\.[ \t]+(.*)$', firstline)
        if m is not None:
            number, firstline = m.group(1,2)
        withcleanedfirstline = [firstline]
        withcleanedfirstline.extend(self.lines[1:])
        return PItem(defaultInnerParse(withcleanedfirstline), number=number)

class Description(Linegroup):
    """
    *Description* explain a word in a gloassary
    """
    def __init__(self):
        Linegroup.__init__(self)

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith(u'*')

    def parse(self):
        if len(self.lines) < 1:
            return PLeaf('')
        text = u'\n'.join(self.lines).strip()
        while text.startswith(u'*'):
            text = text[1:]
        keyrest = text.split(u'*', 1)
        if len(keyrest) < 2:
            # No terminating *, fall back to use the first space
            keyrest = text.split(u' ', 1)
        if len(keyrest) < 2:
            # No space either. Use line.
            keyrest = (text, "")
        key = keyrest[0]
        rest = keyrest[1]
        return PDescription(defaultInnerParse([key.strip()]),
                            defaultInnerParse([rest.strip()]));

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
                        current = linegroup()
                        current.appendline(line)
                        handled = True
            if not handled:
                if not current.rejectcontinuation(line):
                    current.appendline(line)
                else:
                    groups.append(current)
                    current = Paragraph()
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

### Features used by Dokuforge
dffeatures =  [Paragraph, Heading, Author, Subheading, Item, EnumerateItem, Description, Ednote]

def dfLineGroupParser(text):
    """
    @type text: unicode
    """
    groups = grouplines(text.splitlines(), dffeatures)
    ptrees = [g.parse() for g in groups]
    ptrees = groupItems(ptrees)
    ptrees = removeEmpty(ptrees)
    return PSequence(ptrees)
