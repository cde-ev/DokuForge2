# -*- coding: utf-8 -*-
import dataclasses
import functools
import itertools
import textwrap
import math
import re
import typing

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

@dataclasses.dataclass
class Estimate:
    chars: int
    ednotechars: int
    weightedchars: float
    blobs: int

    # The following constants must be float in Py2.X to avoid int division.
    charsperpage = 3000.0
    charsperline = 80.0
    blobsperpage = 3.0

    @classmethod
    def fromText(cls, s: str) -> "Estimate":
        n = len(s)
        return cls(n, 0, n, 0)

    @classmethod
    def fromParagraph(cls, s: str) -> "Estimate":
        return cls.fromText(s).fullline()

    @classmethod
    def fromTitle(cls, s: str) -> "Estimate":
        n = len(s)
        wc = math.ceil(n / cls.charsperline) * cls.charsperline * 2
        return cls(n, 0, wc, 0)

    @classmethod
    def fromEdnote(cls, s: str) -> "Estimate":
        return cls(0, len(s), 0, 0)

    @classmethod
    def fromBlobs(cls, blobs: typing.Sized) -> "Estimate":
        return cls(0, 0, 0, len(blobs))

    @classmethod
    def fromNothing(cls) -> "Estimate":
        return cls(0, 0, 0, 0)

    @classmethod
    def emptyLines(cls, linecount: float = 1) -> "Estimate":
        return cls(0, 0, cls.charsperline * linecount, 0)

    @property
    def pages(self) -> float:
        return self.weightedchars / self.charsperpage

    @property
    def ednotepages(self) -> float:
        return self.ednotechars / self.charsperpage

    @property
    def blobpages(self) -> float:
        return self.blobs / self.blobsperpage

    def fullline(self) -> "Estimate":
        weightedchars = math.ceil(self.weightedchars / self.charsperline) \
                * self.charsperline
        return Estimate(self.chars, self.ednotechars, weightedchars, self.blobs)

    def __add__(self, other: "Estimate") -> "Estimate":
        return Estimate(self.chars + other.chars,
                        self.ednotechars + other.ednotechars,
                        self.weightedchars + other.weightedchars,
                        self.blobs + other.blobs)

    def __mul__(self, num: int) -> "Estimate":
        return Estimate(num * self.chars, num * self.ednotechars,
                        num * self.weightedchars, num * self.blobs)

    __rmul__ = __mul__


T = typing.TypeVar('T')
def intersperse(iterable: typing.Iterable[T], delimiter: T) -> \
        typing.Iterable[T]:
    it = iter(iterable)
    for x in it:
        yield x
        break
    for x in it:
        yield delimiter
        yield x

class Escaper:
    def __init__(self, sequence: str, escaped: str) -> None:
        self.sequence = sequence
        self.escaped = escaped

    def __call__(self, word: str) -> typing.Iterable[str]:
        return intersperse(word.split(self.sequence), self.escaped)


def acronym(word: str) -> typing.Iterable[str]:
    """
    All-capital words should be displayed in smaller font.
    But don't mangle things like 'T-Shirt' or 'E-Mail'.
    """
    if len(word) > 1 and word.isalpha() and word.isupper():
        word = '\\acronym{%s}' % word
    yield word


def standardAbbreviations(word: str) -> typing.Iterable[str]:
    """
    Do spacing for standard abbreviations.
    """
    abb = {
    # FIXME we want '~\dots{}' in nearly every case
        '...': '\\dots{}',
        'bzw.': 'bzw.',
        'ca.': 'ca.',
        'd.h.': 'd.\\,h.',
        'etc.': 'etc.',
        'f.': 'f.',
        'ff.': 'ff.',
        'n.Chr.': 'n.\\,Chr.',
        'o.Ä.': 'o.\\,Ä.',
        's.o.': 's.\\,o.',
        'sog.': 'sog.',
        's.u.': 's.\\,u.',
        'u.a.': 'u.\\,a.',
        'v.Chr.': 'v.\\,Chr.',
        'vgl.': 'vgl.',
        'z.B.': 'z.\\,B.'}

    yield abb.get(word, word)

splitEllipsis = Escaper("...", "...")
# Replace the ellipsis symbol ... by \dots


def naturalNumbers(word: str) -> typing.Iterable[str]:
    """
    Special Spacing for numbers.
    """
    # FIXME negative numbers only work because '-' currently is a separator
    # FIXME we want some special spacing around numbers:
    #       - a number followed by a dot wants a thin space: '21.\,regiment'
    #       - a number followed by a unit wants a thin space: 'weight 67\,kg'
    #       - a number followed by a percent sign wants a thin space: '51\,\%'
    if not re.match('^[0-9]+$', word):
        yield word
    else:
        value = int(word)
        if value < 10000:
            # no special typesetting for 4 digits only
            yield "%d" % value
        else:
            result = ''
            while value >= 1000:
                threedigits = value % 1000
                result = '\\,%03d%s' % (threedigits, result)
                value = value // 1000
            yield '%d%s' % (value, result)


def openQuotationMark(word: str) -> typing.Iterable[str]:
    if len(word) > 1 and word.startswith('"'):
        yield '"`'
        word = word[1:]
    yield word


def closeQuotationMark(word: str) -> typing.Iterable[str]:
    if len(word) > 1 and word.endswith('"'):
        yield word[:-1]
        yield '"\''
    else:
        yield word


def fullStop(word: str) -> typing.Iterable[str]:
    if len(word) > 1 and word.endswith('.'):
        yield word[:-1]
        yield '.'
    else:
        yield word

percent = Escaper("%", "\\%")

ampersand = Escaper("&", "\\&")

hashmark = Escaper("#", "\\#")

caret = Escaper("^", "\\caret{}")

quote = Escaper("'", "'")

class EscapeCommands:
    """
    Mark all controll sequence tokens as forbidden, except
    a list of known good commands.
    """
    escapechar = "\\"
    allowed = set("\\" + symbol for symbol in [
        # produced by our own microtypography or otherwise essential
        ' ', ',', '%', 'dots', '\\', '"', 'acronym', '&',
        '#', 'caret',
        # other allowed commands; FIXME: complete and put to a separate file
        ## list of useful math commands mostly taken
        ## from 'A Guide To LaTeX' by Kopka
        ## greek letters
        'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta',
        'eta', 'theta', 'iota', 'kappa', 'lambda', 'mu',
        'nu', 'xi', 'pi', 'rho', 'sigma', 'tau', 'upsilon',
        'phi', 'chi', 'psi', 'omega', 'Gamma', 'Delta',
        'Theta', 'Lambda', 'Xi', 'Pi', 'Sigma', 'Phi', 'Psi',
        'Omega', 'varepsilon', 'vartheta', 'varpi', 'varrho',
        'varsigma', 'varphi',
        ## math layout
        'frac', 'sqrt', 'sum', 'int', 'ldots', 'cdots',
        'vdots', 'ddots', 'oint', 'prod', 'coprod'
        ## math symbols
        'pm', 'cap', 'circ', 'bigcirc', 'mp', 'cup', 'bullet',
        'Box', 'times', 'uplus', 'diamond', 'Diamond', 'div',
        'sqcap', 'bigtriangleup', 'cdot', 'sqcup',
        'bigtriangledown', 'ast', 'vee', 'unlhd', 'triangleleft',
        'star', 'wedge', 'unrhd', 'triangleright', 'dagger',
        'oplus', 'oslash', 'setminus', 'ddagger', 'ominus',
        'odot', 'wr', 'amalg', 'otimes',
        ## math relations
        'le', 'leq', 'ge', 'geq', 'neq', 'sim', 'll', 'gg',
        'doteq', 'simeq', 'subset', 'supset', 'approx', 'asymp',
        'subseteq', 'supseteq', 'cong', 'smile', 'sqsubset',
        'sqsupset', 'equiv', 'frown', 'sqsubseteq', 'sqsupseteq',
        'propto', 'bowtie', 'in', 'ni', 'prec', 'succ',
        'vdash', 'dashv', 'preceq', 'succeq', 'models', 'perp',
        'parallel', 'mid',
        ## negations
        'not', 'notin',
        ## arrows
        'leftarrow', 'gets', 'longleftarrow', 'uparrow',
        'Leftarrow', 'Longleftarrow', 'Uparrow', 'rightarrow',
        'to', 'longrightarrow', 'downarrow', 'Rightarrow',
        'Longrightarrow', 'Downarrow', 'leftrightarrow',
        'longleftrightarrow', 'updownarrow', 'Leftrightarrow',
        'Longleftrightarrow', 'Updownarrow', 'mapsto', 'longmapsto',
        'nearrow', 'hookleftarrow', 'hookrightarrow', 'searrow',
        'leftharpoonup', 'rightharpoonup', 'swarrow',
        'leftharpoondown', 'rightharpoondown', 'nwarrow',
        'rightleftharpoons', 'leadsto',
        ## various symbols
        'aleph', 'prime', 'forall', 'hbar', 'emptyset',
        'exists', 'imath', 'nablaa', 'neg', 'triangle', 'jmath',
        'surd', 'flat', 'clubsuit', 'ell', 'partial', 'natural',
        'diamondsuit', 'wp', 'top', 'sharp', 'heartsuit', 'Re',
        'bot', 'spadesuit', 'Im', 'vdash', 'angle', 'Join',
        'mho', 'dashv', 'backslash', 'infty',
        ## big symbols
        'bigcap', 'bigodot', 'bigcup', 'bigotimes', 'bigsqcup',
        'bigoplus', 'bigvee', 'biguplus', 'bigwedge',
        ## function names
        'arccos', 'cosh', 'det', 'inf', 'limsup', 'Pr', 'tan',
        'arcsin', 'cot', 'dim', 'ker', 'ln', 'sec', 'tanh',
        'arctan', 'coth', 'exp', 'lg', 'log', 'sin', 'arg',
        'csc', 'gcd', 'lim', 'max', 'sinh', 'cos', 'deg',
        'hom', 'liminf', 'min', 'sup',
        ## accents
        'hat', 'breve', 'grave', 'bar', 'check', 'acute',
        'ti1de', 'vec', 'dot', 'ddot', 'mathring',
        ## parens
        'left', 'right', 'lfloor', 'rfloor', 'lceil', 'rceil',
        'langle', 'rangle',
        ## misc
        'stackrel', 'binom', 'mathbb'
        # FIXME think about including environments, these can come up in
        # complex mathematical formulas, but they could also be abused (more in
        # the "we don't want users to make typesetting decisions" style of
        # misuse, than anything critical).
        # ## environments
        # 'begin', 'end',
    ])

    command_re = re.compile("(%s(?:[a-zA-Z]+|.))" % re.escape(escapechar))

    def forbid(self, word: str) -> str:
        return '\\forbidden' + word

    def __call__(self, word: str) -> typing.Iterable[str]:
        for part in self.command_re.split(word):
            if part.startswith(self.escapechar):
                if part in self.allowed:
                    yield part
                elif part == self.escapechar:
                    # Oh, a backslash at end of input;
                    # maybe we broke into words incorrectly,
                    # so just return something safe.
                    yield '\\@\\textbackslash{}'
                else:
                    yield self.forbid(part)
            else:
                yield part

escapeCommands = EscapeCommands()

escapeEndEdnote = Escaper("\\end{ednote}", "|end{ednote}")
# Escpage the string \\end{ednote}, so that ednotes end
# where we expect them to end.

class SplitSeparators:
    def __init__(self, separators: str) -> None:
        self.splitre = re.compile("([%s])" % re.escape(separators))

    def __call__(self, word: str) -> typing.Iterable[str]:
        return self.splitre.split(word)


MicrotypeFeature = typing.Callable[[str], typing.Iterable[str]]


def applyMicrotypefeatures(wordlist: typing.Iterable[str],
                           featurelist: typing.Iterable[MicrotypeFeature]) -> \
        str:
    """
    sequentially apply (in the sense wordlist >>= feature)
    the features to the wordlist. Return the concatenation
    of the result.
    """
    for feature in featurelist:
        wordlistlist = []
        for word in wordlist:
            assert isinstance(word, str)
            wordlistlist.append(feature(word))
        wordlist = itertools.chain(*wordlistlist)
    return ''.join(wordlist)


def defaultMicrotype(text: str) -> str:
    assert isinstance(text, str)
    # FIXME '-' should not be a separator so we are able to detect dashes '--'
    #       however this will break NaturalNumbers for negative inputs
    separators = ' \t,;()-\n' # no point, might be in abbreviations
    features: typing.List[MicrotypeFeature] = [
        SplitSeparators(separators), splitEllipsis, percent, ampersand, caret,
        hashmark, quote, standardAbbreviations, fullStop, openQuotationMark,
        closeQuotationMark, acronym, naturalNumbers, escapeCommands
    ]
    return applyMicrotypefeatures([text], features)


def mathMicrotype(text: str) -> str:
    # FIXME we want to substitute '...' -> '\dots{}' in math mode too
    features: typing.List[MicrotypeFeature] = [
        percent, hashmark, naturalNumbers, escapeCommands
    ]
    return applyMicrotypefeatures([text], features)


def ednoteMicrotype(text: str) -> str:
    return applyMicrotypefeatures([text], [escapeEndEdnote])


def isemptyline(line: str) -> bool:
    return bool(re.match('^[ \t]*$', line))


def wrap(text: str, subsequent_indent: str = '') -> str:
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
    def debug(self) -> typing.Any:
        return None

    def isEmpty(self) -> bool:
        return False

    def toTex(self) -> str:
        """
        return a tex-representation of the parsed object.
        """
        raise NotImplementedError

    def toHtml(self) -> str:
        """
        return a html-representation of the parsed object.
        """
        raise NotImplementedError

    def toDF(self) -> str:
        """
        return a canonical representation of the text in
        dokuforge markup language.
        """
        raise NotImplementedError

    def toEstimate(self) -> Estimate:
        raise NotImplementedError

class PSequence(PTree):
    """
    A piece of text formed by juxtaposition of several
    Parse Trees (usually paragraphs).
    """
    def __init__(self, parts: typing.List[PTree]) -> None:
        self.parts = parts

    def debug(self) -> typing.Any:
        return ('Sequence', [part.debug() for part in self.parts])

    def toTex(self) -> str:
        result = ''
        for part in self.parts:
            result = result + part.toTex()
        return result

    def toHtml(self) -> str:
        result = ''
        for part in self.parts:
            result = result + part.toHtml()
        return result

    def toDF(self) -> str:
        result = ''
        for part in self.parts:
            result = result + part.toDF()
        return result

    def toEstimate(self) -> Estimate:
        return functools.reduce(lambda a, b: a + b,
                      (part.toEstimate() for part in self.parts),
                      Estimate.fromNothing())

class PLeaf(PTree):
    """
    A piece of text that contains no further substructure.
    """
    def __init__(self, text: str) -> None:
        assert isinstance(text, str)
        self.text = text

    def debug(self) -> typing.Any:
        return self.text

    def isEmpty(self) -> bool:
        return isemptyline(self.text)

    def toTex(self) -> str:
        return defaultMicrotype(self.text)

    def toHtml(self) -> str:
        result = self.text
        result = result.replace('&', '&amp;')
        result = result.replace('<', '&lt;')
        result = result.replace('>', '&gt;')
        result = result.replace('"', '&#34;')
        result = result.replace("'", '&#39;')
        return result

    def toDF(self) -> str:
        return self.text

    def toEstimate(self) -> Estimate:
        return Estimate.fromText(self.text)

class PEmph(PTree):
    """
    An emphasized piece of text.
    """
    def __init__(self, text: str) -> None:
        self.text = PLeaf(text)

    def debug(self) -> typing.Any:
        return ('emph', self.text.text)

    def toTex(self) -> str:
        return '\\emph{%s}' % self.text.toTex()

    def toHtml(self) -> str:
        return '<em>%s</em>' % self.text.toHtml()

    def toDF(self) -> str:
        return '_%s_' % self.text.toDF()

    def toEstimate(self) -> Estimate:
        return self.text.toEstimate()

class PMath(PTree):
    """
    An non-display math area.
    """
    def __init__(self, text: str) -> None:
        self.text = PLeaf(text)

    def debug(self) -> typing.Any:
        return ('math', self.text.text)

    def toTex(self) -> str:
        return '$%1s$' % mathMicrotype(self.text.text)

    def toHtml(self) -> str:
        return '$%1s$' % self.text.toHtml()

    def toDF(self) -> str:
        return '$%1s$' % self.text.toDF()

    def toEstimate(self) -> Estimate:
        return self.text.toEstimate()

class PDisplayMath(PTree):
    """
    An display math area.
    """
    def __init__(self, text: str) -> None:
        self.text = PLeaf(text)

    def debug(self) -> typing.Any:
        return ('displaymath', self.text.text)

    def toTex(self) -> str:
        return '\\[%1s\\]' % mathMicrotype(self.text.text)

    def toHtml(self) -> str:
        return "<div class=\"displaymath\">$$%1s$$</div>" % self.text.toHtml()

    def toDF(self) -> str:
        return '$$%1s$$' % self.text.toDF()

    def toEstimate(self) -> Estimate:
        return Estimate.fromText(self.text.text).fullline() + \
                Estimate.emptyLines(2)

class PEdnote(PTree):
    """
    An Ednote; contents are compeletly unchanged.
    """
    def __init__(self, text: str) -> None:
        self.text = PLeaf(text)

    def isEmpty(self) -> bool:
        # the mere fact that there was an Ednote
        # is already worth mentioning
        return False

    def debug(self) -> typing.Any:
        return ('Ednote', self.text.text)

    def toTex(self) -> str:
        return '\n\\begin{ednote}\n%s\n\\end{ednote}\n' % \
                ednoteMicrotype(self.text.text)

    def toHtml(self) -> str:
        return '\n<pre class="ednote">\n%s\n</pre>\n' % self.text.toHtml()

    def toDF(self) -> str:
        # find a bracket combination not in the text
        text = self.text.toDF()
        n = 1
        while text.find('}' * n) >= 0:
            n += 1
        return '\n%s\n%s\n%s\n' % ('{' * n, text, '}' * n)

    def toEstimate(self) -> Estimate:
        return Estimate.fromEdnote(self.text.text)

class PParagraph(PTree):
    def __init__(self, subtree: PTree) -> None:
        self.it = subtree

    def debug(self) -> typing.Any:
        return ('Paragraph', self.it.debug())

    def isEmpty(self) -> bool:
        return self.it.isEmpty()

    def toTex(self) -> str:
        return '\n%s\n' % wrap(self.it.toTex())

    def toHtml(self) -> str:
        return '\n<p>\n'  + self.it.toHtml() + '\n</p>\n'

    def toDF(self) -> str:
        return '\n\n%s\n' % self.it.toDF()

    def toEstimate(self) -> Estimate:
        return self.it.toEstimate().fullline()

class PHeading(PTree):
    def __init__(self, title: str, level: int) -> None:
        self.title = PLeaf(title)
        self.level = level

    def debug(self) -> typing.Any:
        return ('Heading', self.level, self.getTitle())

    def toTex(self) -> str:
        return '\n\\%ssection{%s}\n' % ("sub" * self.level, self.title.toTex())

    def toHtml(self) -> str:
        n = self.level + 1
        return '\n<h%d>%s</h%d>\n' % (n, self.title.toHtml(), n)

    def toDF(self) -> str:
        n = self.level + 1
        return '\n\n%s%s%s' % ('[' * n, self.title.toDF(), ']' * n)

    def getLevel(self) -> int:
        return self.level

    def getTitle(self) -> str:
        return self.title.text

    def toEstimate(self) -> Estimate:
        return Estimate.fromTitle(self.getTitle())

class PAuthor(PTree):
    def __init__(self, author: str) -> None:
        self.author = PLeaf(author)

    def getAuthor(self) -> str:
        return self.author.text

    def debug(self) -> typing.Any:
        return ('Author', self.getAuthor())

    def toTex(self) -> str:
        return '\\authors{%s}\n' % self.author.toTex()

    def toHtml(self) -> str:
        return '<i>%s</i>' % self.author.toHtml()

    def toDF(self) -> str:
        return '\n(%s)' % self.author.toDF()

    def toEstimate(self) -> Estimate:
        return Estimate.fromParagraph(self.getAuthor())

class PDescription(PTree):
    def __init__(self, key: PTree, value: PTree) -> None:
        self.key = key
        self.value = value

    def debug(self) -> typing.Any:
        return ('Description', self.key.debug(), self.value.debug())

    def toTex(self) -> str:
        return '\n' + wrap('\\paragraph{' + self.key.toTex() + '} ' + self.value.toTex()) + '\n'

    def toHtml(self) -> str:
        return '\n<p><b>' + self.key.toHtml() + '</b> ' + self.value.toHtml() + '\n</p>\n'

    def toDF(self) -> str:
        return '\n\n*%1s* %s' % (self.key.toDF(), self.value.toDF())

    def toEstimate(self) -> Estimate:
        return self.key.toEstimate() + self.value.toEstimate()

class PItemize(PTree):
    def __init__(self, items: typing.List["PItem"]) -> None:
        self.items = items
        self.isEnum = False
        if len(self.items) > 0:
            self.isEnum = self.items[0].isEnumerate()

    def debug(self) -> typing.Any:
        return ('Itemize', [item.debug() for item in self.items])

    def isEnumerate(self) -> bool:
        return self.isEnum

    def toTex(self) -> str:
        itemtype = 'enumerate' if self.isEnumerate() else 'itemize'
        body = ''.join(item.toTex() for item in self.items)
        return '\n\\begin{%s}%s\n\\end{%s}\n' % (itemtype, body, itemtype)

    def toHtml(self) -> str:
        itemtype =  'ul'
        if self.isEnumerate():
            itemtype = 'ol'
        result = '\n<%s>' % itemtype
        for item in self.items:
            result = result + item.toHtml()
        result = result + ('\n</%s>\n' % itemtype)
        return result

    def toDF(self) -> str:
        return "\n" + "".join(item.toDF() for item in self.items)

    def toEstimate(self) -> Estimate:
        return functools.reduce(lambda a, b: a + b + Estimate.emptyLines(0.5),
                      [item.toEstimate() for item in self.items],
                      Estimate.fromNothing()) + \
                Estimate.emptyLines(2)

class PItem(PTree):
    def __init__(self, subtree: PTree,
                 number: typing.Optional[str] = None) -> None:
        self.it = subtree
        self.number=number

    def debug(self) -> typing.Any:
        return ('Item', self.it.debug(), self.number)

    def isEnumerate(self) -> bool:
        return self.number is not None

    def toTex(self) -> str:
        body = wrap('\\item ' + self.it.toTex(), subsequent_indent='  ')
        if self.number is None:
            return '\n' + body
        else:
            return '\n%% %s\n%s' % (self.number, body)

    def toHtml(self) -> str:
        return '\n<li> ' + self.it.toHtml()

    def toDF(self) -> str:
        if self.number is None:
            return '\n- ' + self.it.toDF()
        else:
            return '\n%s. %s' % (self.number, self.it.toDF())

    def toEstimate(self) -> Estimate:
        return self.it.toEstimate()

class Chargroup:
    """
    Abstract class where all char-groups inherit from.

    A char group is a group of sucessive characters within
    a line group, forming a logical unit within that line
    group, like an emphasis, or a math environment.
    """
    def __init__(self, initial: typing.Optional[str] = None) -> None:
        self.text = ''
        if initial is not None:
            self.append(initial)

    def append(self, chars: str) -> None:
        """
        Append the given (possibly empty) sequence of chars to that group.
        """
        self.text = self.text + chars

    def debug(self) -> typing.Any:
        return (self.__class__.__name__, self.text)

    def parse(self) -> PTree:
        return PLeaf(self.text)

    @classmethod
    def startshere(cls, char: str,
                   lookahead: typing.Optional[str] = None) -> bool:
        """
        Return True, if a new chargroup of this type starts at the
        given char, which itself is followed by the lookahead.
        The lookahead is None, if the given char is the last char
        of the line group.
        """
        return False

    def enforcecontinuation(self, char: str) -> bool:
        """
        Return True, if if this group insists in taking that next character,
        regardless of whether other groups might start here.
        """
        return False

    def rejectcontinuation(self, char: str) -> bool:
        """
        Return True, if this group refuses to accept that next character, even
        if that means a new Simplegroup has to be started.
        """
        return False

class Simplegroup(Chargroup):
    """
    The default char group, without any special markup.
    """
    def __init__(self, initial: typing.Optional[str] = None) -> None:
        Chargroup.__init__(self, initial=initial)

class Emphgroup(Chargroup):
    """
    The group for _emphasized text_.
    """
    def __init__(self, initial: typing.Optional[str] = None) -> None:
        Chargroup.__init__(self, initial=initial)

    @classmethod
    def startshere(cls, char: str,
                   lookahead: typing.Optional[str] = None) -> bool:
        return char == '_'

    def rejectcontinuation(self, char: str) -> bool:
        if len(self.text) < 2:
            return False
        return self.text.endswith('_')

    def enforcecontinuation(self, char: str) -> bool:
        ## Force to get the closing _
        if self.rejectcontinuation(char):
            return False
        return char == '_'

    def parse(self) -> PTree:
        assert self.text.startswith("_")
        if self.text.endswith("_"):
            return PEmph(self.text[1:-1])
        else:
            return PEmph(self.text[1:])

class Mathgroup(Chargroup):
    """
    The group for simple (non dislay) math,
    like $a^2 + b^2$.
    """
    def __init__(self, initial: typing.Optional[str] = None) -> None:
        self.trailingbackslashs = 0
        self.done = False
        self.count = 0
        Chargroup.__init__(self, initial=initial)

    @classmethod
    def startshere(cls, char: str,
                   lookahead: typing.Optional[str] = None) -> bool:
        return char == '$' and lookahead != '$'

    def append(self, chars: str) -> None:
        for c in chars:
            self.text = self.text + c
            self.count = self.count + 1
            if c == '$' and self.count > 2:
                if self.trailingbackslashs % 2 == 0:
                    self.done = True

            if c == '\\':
                self.trailingbackslashs = self.trailingbackslashs + 1
            else:
                self.trailingbackslashs = 0

    def enforcecontinuation(self, char: str) -> bool:
        return not self.done

    def rejectcontinuation(self, char: str) -> bool:
        return self.done

    def parse(self) -> PTree:
        result = self.text
        if result.startswith('$'):
            result = result[1:]
        if result.endswith('$'):
            result = result[:-1]
        return PMath(result)


class DisplayMathGroup(Chargroup):
    """
    The group for display math
    like $$ a^2 + b^2 = c^2$$
    """
    def __init__(self, initial: typing.Optional[str] = None) -> None:
        self.done = False
        self.trailingbackslashs = 0
        self.trailingdollar = 0
        self.count = 0
        Chargroup.__init__(self, initial=initial)

    @classmethod
    def startshere(cls, char: str,
                   lookahead: typing.Optional[str] = None) -> bool:
        return char == '$' and lookahead == '$'

    def append(self, chars: str) -> None:
        for c in chars:
            self.text = self.text + c
            self.count = self.count + 1
            if c == '$' and self.count > 2:
                if self.trailingdollar == 1:
                    self.done = True
                elif self.trailingbackslashs % 2 == 0:
                    self.trailingbackslashs=0
                    self.trailingdollar += 1
                else:
                    self.trailingbackslashs = 0
                    self.trailingdollar = 0
            elif c == '\\':
                self.trailingdollar = 0
                self.trailingbackslashs += 1
            else:
                self.trailingdollar = 0
                self.trailingbackslashs = 0

    def enforcecontinuation(self, char: str) -> bool:
        return not self.done

    def rejectcontinuation(self, char: str) -> bool:
        return self.done

    def parse(self) -> PTree:
        result = self.text
        if result.startswith('$$'):
            result = result[2:]
        if result.endswith('$$'):
            result = result[:-2]
        if result.endswith('$'):
            result += ' '
        return PDisplayMath(result)


def groupchars(text: str,
               supportedgroups: typing.Iterable[typing.Type[Chargroup]]) -> \
        typing.List[Chargroup]:
    """
    Given a string (considered a list of chars) and a list of
    Chargroups to support, group the chars accordingly.
    """
    current: Chargroup = Simplegroup()
    groups: typing.List[Chargroup] = []
    for i in range(len(text)):
        c = text[i]
        lookahead: typing.Optional[str]
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


def defaultInnerParse(lines: typing.List[str]) -> PTree:
    features = [Simplegroup, Emphgroup, Mathgroup, DisplayMathGroup]
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
    def __init__(self) -> None:
        self.lines: typing.List[str] = []

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional["Linegroup"] = None) -> bool:
        """
        Decide if this line starts a new group of the given type,
        assuming that it occurs after the group provided in in
        the optional argument.
        """
        return False

    def rejectcontinuation(self, line: str) -> bool:
        """
        Decide that this group definitely does not want any more lines,
        and, in the worst case, a new paragraph has to be started.
        """
        return False

    def enforcecontinuation(self, line: str) -> bool:
        """
        Decide if this group enforces that the next line belongs to
        the current group, even though it could start a new group.
        Useful for ednotes or similar greedy groups.
        """
        return False

    def parse(self) -> PTree:
        """
        Return a representation of this linegroup as PTree.
        """
        return defaultInnerParse(self.lines)

    def appendline(self, line: str) -> None:
        self.lines.append(line)

    def debug(self) -> typing.Any:
        return (self.__class__.__name__, self.lines)


class Paragraph(Linegroup):
    """
    A standard paragraph. This hopefully should be the most common
    line group in a document.
    """
    def __init__(self) -> None:
        Linegroup.__init__(self)

    def appendline(self, line: str) -> None:
        if not isemptyline(line):
            Linegroup.appendline(self, line)

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional[Linegroup] = None) -> bool:
        return isemptyline(line)

    def parse(self) -> PTree:
        return PParagraph(defaultInnerParse(self.lines))


def splitleftbracket(line: str) -> typing.List[str]:
    openings = set(['(', '[', '{'])
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


def splitrightbracket(line: str) -> typing.List[str]:
    line = line.rstrip()
    closings = set([')', ']', '}'])
    bracket, rest = '', ''
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


def isMirrorBracket(firstline: str, lastline: str) -> bool:
    """
    Return True iff lastline ends with the matching
    bigbracket to the one the firstline starts with.
    """
    closing = {'{': '}', '(': ')', '<': '>', '[': ']'}

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
    def __init__(self) -> None:
        Linegroup.__init__(self)

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional[Linegroup] = None) -> bool:
        return line.startswith('{')

    def enforcecontinuation(self, line: str) -> bool:
        if len(self.lines) < 1:
            return True
        if isMirrorBracket(self.lines[0], self.lines[-1]):
           return False
        return True

    def rejectcontinuation(self, line: str) -> bool:
        return not self.enforcecontinuation(line)

    def parse(self) -> PTree:
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
            start += '\n'
        end = splitrightbracket(self.lines[-1])[0]

        if len(self.lines) > 2 and len(end) != 0:
            end = '\n' + end

        return PEdnote(start + '\n'.join(self.lines[1:-1]) + end)


class Heading(Linegroup):
    """
    Headings, marked [As such] in dokuforge
    """
    def __init__(self) -> None:
        Linegroup.__init__(self)

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional[Linegroup] = None) -> bool:
        return line.startswith('[') and not line.startswith('[[')

    def enforcecontinuation(self, line: str) -> bool:
        if isemptyline(line):
            return False
        if len(self.lines) < 1:
            return True
        return ']' not in set(self.lines[-1])

    def rejectcontinuation(self, line: str) -> bool:
        return not self.enforcecontinuation(line)

    def getTitle(self) -> str:
        title = ' '.join(self.lines)
        title = title.lstrip('[')
        title = title.rstrip(' \t')
        title = title.rstrip(']')
        return title

    def parse(self) -> PTree:
        return PHeading(self.getTitle(), 0)

class Subheading(Heading):
    """
    Subheadings, markes [[as such]] in dokuforge
    """
    def __init__(self) -> None:
        Heading.__init__(self)

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional[Linegroup] = None) -> bool:
        return line.startswith('[[') and not line.startswith('[[[')

    def parse(self) -> PTree:
        return PHeading(self.getTitle(), 1)

class Author(Linegroup):
    """
    List of authors, marked (Some Author) in dokuforge
    """
    def __init__(self) -> None:
        Linegroup.__init__(self)

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional[Linegroup] = None) -> bool:
        return line.startswith('(') and isinstance(after, Heading)

    def enforcecontinuation(self, line: str) -> bool:
        if isemptyline(line):
            return False
        if len(self.lines) < 1:
            return True
        return ')' not in set(self.lines[-1])

    def rejectcontinuation(self, line: str) -> bool:
        return not self.enforcecontinuation(line)

    def parse(self) -> PTree:
        author = ' '.join(self.lines)
        author = author.lstrip('(')
        author = author.rstrip(' \t')
        author = author.rstrip(')')
        return PAuthor(author)

class Item(Linegroup):
    """
    An entry of an itemization, marked as
    - first
    - second
    - third
    in DokuForge.
    """
    def __init__(self) -> None:
        Linegroup.__init__(self)

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional[Linegroup] = None) -> bool:
        return line.startswith('- ')

    def parse(self) -> PTree:
        if len(self.lines) < 1:
            return PItem(defaultInnerParse(self.lines))
        firstline = self.lines[0]
        if firstline.startswith('- '):
            firstline = firstline[2:]
        withcleanedfirstline = [firstline]
        withcleanedfirstline.extend(self.lines[1:])
        return PItem(defaultInnerParse(withcleanedfirstline))

class EnumerateItem(Linegroup):
    """
    An entry in an enumeration, marked as
    1. First
    2. Second
    3. and so on
    in DokuForge
    """
    def __init__(self) -> None:
        Linegroup.__init__(self)

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional[Linegroup] = None) -> bool:
        return bool(re.match('^[0-9]+\\.[ \t]', line))

    def parse(self) -> PTree:
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
    def __init__(self) -> None:
        Linegroup.__init__(self)

    @classmethod
    def startshere(cls, line: str,
                   after: typing.Optional[Linegroup] = None) -> bool:
        return line.startswith('*')

    def parse(self) -> PTree:
        if len(self.lines) < 1:
            return PLeaf('')
        text = '\n'.join(self.lines).strip()
        while text.startswith('*'):
            text = text[1:]
        keyrest = text.split('*', 1)
        if len(keyrest) < 2:
            # No terminating *, fall back to use the first space
            keyrest = text.split(' ', 1)
        if len(keyrest) < 2:
            # No space either. Use line.
            key, rest = text, ""
        else:
            key, rest = keyrest[:2]
        return PDescription(defaultInnerParse([key.strip()]),
                            defaultInnerParse([rest.strip()]));


def grouplines(lines: typing.Iterable[str],
               supportedgroups: typing.Iterable[typing.Type[Linegroup]]) -> \
        typing.List[Linegroup]:
    """
    Given a list of lines and a list of Linegroup to support, group
    lines accordingly.

    The grouping is done based on the startshere, enforcecontinuatuion,
    and rejectcontinuation methods provided by the supported linegroups.
    """
    current: Linegroup = Paragraph()
    groups: typing.List[Linegroup] = []
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


def removeEmpty(ptrees: typing.List[PTree]) -> typing.List[PTree]:
    """
    Given a list of PTrees, return a list containing the
    same elements but the empty ones.
    """
    result = []
    for ptree in ptrees:
        if not ptree.isEmpty():
            result.append(ptree)
    return result


def groupItems(ptrees: typing.List[PTree]) -> typing.List[PTree]:
    """
    For a given list of PTrees, return the same list, but
    with every sequence of PItems replaced by an PItemize.
    """
    result: typing.List[PTree] = []
    items: typing.List[PItem] = []
    for tree in ptrees:
        if isinstance(tree, PItem):
            items.append(tree)
        else:
            if items:
                result.append(PItemize(items))
                items = []
            result.append(tree)
    if items:
        result.append(PItemize(items))
    return result

### Features used by DokuForge
dffeatures =  [Paragraph, Heading, Author, Subheading, Item, EnumerateItem, Description, Ednote]


def dfLineGroupParser(text: str) -> PSequence:
    groups = grouplines(text.splitlines(), dffeatures)
    ptrees = [g.parse() for g in groups]
    ptrees = groupItems(ptrees)
    ptrees = removeEmpty(ptrees)
    return PSequence(ptrees)

titlefeatures =  [Paragraph]


def dfTitleParser(text: str) -> PSequence:
    groups = grouplines(text.splitlines(), titlefeatures)
    ptrees = [g.parse() for g in groups]
    ptrees = groupItems(ptrees)
    ptrees = removeEmpty(ptrees)
    return PSequence(ptrees)

captionfeatures =  [Paragraph, Item, EnumerateItem, Description, Ednote]


def dfCaptionParser(text: str) -> PSequence:
    groups = grouplines(text.splitlines(), dffeatures)
    ptrees = [g.parse() for g in groups]
    ptrees = groupItems(ptrees)
    ptrees = removeEmpty(ptrees)
    return PSequence(ptrees)
