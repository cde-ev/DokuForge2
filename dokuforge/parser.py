# -*- coding: utf-8 -*-

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
##    export, look at the abstract class MicrotypeFeature, the function
##    defaultMicrotype and the decendents of MicrotypeFeature.

# FIXME add \@ in the appropriate places of the TeX export
#       i.e. whenever the exporter encountered something special

class MicrotypeFeature:
    """
    Abstract class where all word-level microtypographic
    features inherit from.
    """
    @classmethod
    def applies(self, word):
        return False

    @classmethod
    def doit(self, word):
        """
        return a list of processed words, that should be
        treated separately by all following features.
        """
        return [word]

class Acronym(MicrotypeFeature):
    """
    All-capital words should be displayed in smaller font.
    """
    
    @classmethod
    def applies(self, word):
        return len(word) > 0 and word.isupper()

    @classmethod
    def doit(self, word):
        return ['\\acronym{%s}' % word]

class StandardAbbreviations(MicrotypeFeature):
    """
    Do spacing for standard abbreviations.
    """
    abb = { 
    # FIXME we want '~\dots{}' in nearly every case
        '...' : '\\dots{}',
        'bzw.' : 'bzw.',
        'ca.' : 'ca.',
        'd.h.' : 'd.\\,h.',
        'etc.' : 'etc.',
        'f.' : 'f.',
        'ff.' : 'ff.',
        'n.Chr.' : 'n.\\,Chr.',
        u'o.Ä.' : u'o.\,Ä.',
        's.o.' : 's.\\,o.',
        'sog.' : 'sog.',
        's.u.' : 's.\\,u.',
        'u.a.' : 'u.\\,a.',
        'v.Chr.' : 'v.\\,Chr.',
        'vgl.' : 'vgl.',
        'z.B.' : 'z.\\,B.'}

    @classmethod
    def applies(self, word):
        return word in self.abb

    @classmethod
    def doit(self, word):
        return [self.abb[word]]

class SplitEllipsis(MicrotypeFeature):
    """
    Replace the ellipsis symbol ... by \dots
    """
    dots = re.compile('(\\.\\.\\.)')

    @classmethod
    def applies(self, word):
        if self.dots.search(word) is not None:
            return True
        return  False

    @classmethod
    def doit(self, word):
        return self.dots.split(word)

class SplitSpaces(MicrotypeFeature):
    """
    Split at all spaces.
    """
    space = re.compile('( )')

    @classmethod
    def applies(self, word):
        if self.space.search(word) is not None:
            return True
        return False

    @classmethod
    def doit(self, word):
        return self.space.split(word)

class ThinSpaceAfterNumber(MicrotypeFeature):
    """
    Replace all spaces after numbers by \\, and split there.
    """
    numberspace = re.compile('([0-9]+ )')
    allnumberspace = re.compile('^[0-9]+ $')

    @classmethod
    def applies(self, word):
        if self.numberspace.search(word) is not None:
            return True
        return False

    @classmethod
    def doit(self, word):
        tokens = self.numberspace.split(word)
        splitted = []
        for token in tokens:
            if self.allnumberspace.match(token) is not None:
                splitted = splitted + [token[0:-1], '\\,']
            else:
                splitted = splitted + [token]
        return splitted

class NaturalNumbers(MicrotypeFeature):
    """
    Special Spacing for numbers.
    """
    # FIXME negative numbers only work because '-' currently is a separator
    # FIXME we want some special spacing around numbers:
    #       - a number followed by a dot wants a thin space: '21.\,regiment'
    #       - a number followed by a unit wants a thin space: 'weight 67\,kg'
    #       - a number followed by a percent sign wants a thin space: '51\,\%'
    @classmethod
    def applies(self, word):
        return len(word) > 0 and re.match('^[0-9]+$', word)

    @classmethod
    def doit(self, word):
        value = int(word)
        if value < 10000:
            # no special typesetting for 4 digits only
            return ["%d" % value]
        result = ''
        while value >= 1000:
            threedigits = value % 1000
            result = '\\,%03d%s' % (threedigits, result)
            value = value // 1000
        return ['%d%s' % (value, result)]

class OpenQuotationMark(MicrotypeFeature):
    @classmethod
    def applies(self, word):
        return len(word) > 1 and word.startswith('"')

    @classmethod
    def doit(self, word):
        return ['"`', word[1:]]

class CloseQuotationMark(MicrotypeFeature):
    @classmethod
    def applies(self, word):
        return len(word) > 1 and word.endswith('"')

    @classmethod
    def doit(self, word):
        return [word[:-1], '"\'']

class FullStop(MicrotypeFeature):
    @classmethod
    def applies(self, word):
        return len(word) > 1 and word.endswith('.')

    @classmethod
    def doit(self, word):
        return [word[:-1], '.']

class Percent(MicrotypeFeature):
    percent = re.compile('%')
    escaped = re.compile('(\\\\%)')

    @classmethod
    def applies(self, word):
        if self.percent.search(word) is not None:
            return True
        return  False

    @classmethod
    def doit(self, word):
        substitued = self.percent.sub('\\%', word)
        return self.escaped.split(substitued)

class Ampersand(MicrotypeFeature):
    ampersand = re.compile('&')
    escaped = re.compile('(\\\\&)')

    @classmethod
    def applies(self, word):
        if self.ampersand.search(word) is not None:
            return True
        return  False

    @classmethod
    def doit(self, word):
        substitued = self.ampersand.sub('\\&', word)
        return self.escaped.split(substitued)

class Hashmark(MicrotypeFeature):
    hashmark = re.compile('#')
    escaped = re.compile('(\\\\#)')

    @classmethod
    def applies(self, word):
        if self.hashmark.search(word) is not None:
            return True
        return  False

    @classmethod
    def doit(self, word):
        substitued = self.hashmark.sub('\\#', word)
        return self.escaped.split(substitued)

class Caret(MicrotypeFeature):
    caret = re.compile('\\^')
    escaped = re.compile('(\\\\caret{})')

    @classmethod
    def applies(self, word):
        if self.caret.search(word) is not None:
            return True
        return  False

    @classmethod
    def doit(self, word):
        substitued = self.caret.sub('\\caret{}', word)
        return self.escaped.split(substitued)

class Quote(MicrotypeFeature):
    quote = re.compile('\'')
    escaped = re.compile('(\')')

    @classmethod
    def applies(self, word):
        if self.quote.search(word) is not None:
            return True
        return  False

    @classmethod
    def doit(self, word):
        substitued = self.quote.sub('\'', word)
        return self.escaped.split(substitued)

class EscapeCommands(MicrotypeFeature):
    """
    Mark all controll sequence tokens as forbidden, except
    a list of known good commands.
    """
    allowed = [
    # produced by our own microtypography or otherwise essential
    '\\ ', '\\,', '\\%', '\\dots', '\\\\', '\\"', '\\acronym', '\\&',
    '\\#', '\\caret',
    # other allowed commands; FIXME: complete and put to a separate file
    ## list of useful math commands mostly taken
    ## from 'A Guide To LaTeX' by Kopka
    ## greek letters
    '\\alpha', '\\beta', '\\gamma', '\\delta', '\\epsilon', '\\zeta',
    '\\eta', '\\theta', '\\iota', '\\kappa', '\\lambda', '\\mu',
    '\\nu', '\\xi', '\\pi', '\\rho', '\\sigma', '\\tau', '\\upsilon',
    '\\phi', '\\chi', '\\psi', '\\omega', '\\Gamma', '\\Delta',
    '\\Theta', '\\Lambda', '\\Xi', '\\Pi', '\\Sigma', '\\Phi', '\\Psi',
    '\\Omega', '\\varepsilon', '\\vartheta', '\\varpi', '\\varrho',
    '\\varsigma', '\\varphi',
    ## math layout
    '\\frac', '\\sqrt', '\\sum', '\\int', '\\ldots', '\\cdots',
    '\\vdots', '\\ddots', '\\oint', '\\prod', '\\coprod'
    ## math symbols
    '\\pm', '\\cap', '\\circ', '\\bigcirc' '\\mp', '\\cup', '\\bullet',
    '\\Box' '\\times', '\\uplus', '\\diamond', '\\Diamond', '\\div',
    '\\sqcap', '\\bigtriangleup', '\\cdot', '\\sqcup',
    '\\bigtriangledown', '\\ast', '\\vee', '\\unlhd', '\\triangleleft',
    '\\star', '\\wedge', '\\unrhd', '\\triangleright', '\\dagger',
    '\\oplus', '\\oslash', '\\setminus', '\\ddagger', '\\ominus',
    '\\odot', '\\wr', '\\amalg', '\\otimes',
    ## math relations
    '\\le', '\\leq', '\\ge', '\\geq', '\\neq', '\\sim', '\\ll', '\\gg',
    '\\doteq', '\\simeq', '\\subset', '\\supset', '\\approx', '\\asymp',
    '\\subseteq', '\\supseteq', '\\cong', '\\smile', '\\sqsubset',
    '\\sqsupset', '\\equiv', '\\frown', '\\sqsubseteq', '\\sqsupseteq',
    '\\propto', '\\bowtie', '\\in', '\\ni', '\\prec', '\\succ',
    '\\vdash', '\\dashv', '\\preceq', '\\succeq', '\\models', '\\perp',
    '\\parallel', '\\mid',
    ## negations
    '\\not', '\\notin',
    ## arrows
    '\\leftarrow', '\\gets', '\\longleftarrow', '\\uparrow',
    '\\Leftarrow', '\\Longleftarrow', '\\Uparrow', '\\rightarrow',
    '\\to', '\\longrightarrow', '\\downarrow', '\\Rightarrow',
    '\\Longrightarrow', '\\Downarrow', '\\leftrightarrow',
    '\\longleftrightarrow', '\\updownarrow', '\\Leftrightarrow',
    '\\Longleftrightarrow', '\\Updownarrow', '\\mapsto', '\\longmapsto',
    '\\nearrow', '\\hookleftarrow', '\\hookrightarrow', '\\searrow',
    '\\leftharpoonup', '\\rightharpoonup', '\\swarrow',
    '\\leftharpoondown', '\\rightharpoondown', '\\nwarrow',
    '\\rightleftharpoons', '\\leadsto',
    ## various symbols
    '\\aleph', '\\prime', '\\forall', '\\hbar', '\\emptyset',
    '\\exists', '\\imath', '\\nablaa', '\\neg', '\\triangle', '\\jmath',
    '\\surd', '\\flat', '\\clubsuit', '\\ell', '\\partial', '\\natural',
    '\\diamondsuit', '\\wp', '\\top', '\\sharp', '\\heartsuit', '\\Re',
    '\\bot', '\\spadesuit', '\\Im', '\\vdash', '\\angle', '\\Join',
    '\\mho', '\\dashv', '\\backslash', '\\infty',
    ## big symbols
    '\\bigcap', '\\bigodot', '\\bigcup', '\\bigotimes', '\\bigsqcup',
    '\\bigoplus', '\\bigvee', '\\biguplus', '\\bigwedge',
    ## function names
    '\\arccos', '\\cosh', '\\det', '\\inf' '\\limsup', '\\Pr', '\\tan',
    '\\arcsin', '\\cot', '\\dim', '\\ker', '\\ln', '\\sec', '\\tanh',
    '\\arctan', '\\coth', '\\exp', '\\lg', '\\log', '\\sin', '\\arg',
    '\\csc', '\\gcd', '\\lim', '\\max', '\\sinh', '\\cos', '\\deg',
    '\\hom', '\\liminf', '\\min', '\\sup',
    ## accents
    '\\hat', '\\breve', '\\grave', '\\bar', '\\check', '\\acute',
    '\\ti1de', '\\vec', '\\dot', '\\ddot', '\\mathring',
    ## parens
    '\\left', '\\right', '\\lfloor', '\\rfloor', '\\lceil', '\\rceil',
    '\\langle', '\\rangle',
    ## misc
    '\\stackrel', '\\binom', '\\mathbb'
    # FIXME think about including environments, these can come up in complex
    # mathematical formulas, but they could also be abused (more in the "we
    # don't want users to make typesetting decisions" style of misuse, than
    # anything critical).
    # ## environments
    # '\\begin', '\\end',
    ]

    @classmethod
    def isOK(self, word):
        return word in self.allowed

    @classmethod
    def forbid(self, word):
        return '\\forbidden' + word

    @classmethod
    def isEscapeChar(self, c):
        return c == '\\'

    @classmethod
    def isLetter(self, c):
        return ('a' <= c and c <= 'z') or ('A' <= c and c <= 'Z')

    @classmethod
    def scanControlSequence(self, sofar, unlexed):
        if len(sofar) == 1:
            if len(unlexed) == 0:
                # Oh, a backslash at end of input;
                # maybe we broke into words incorrectly,
                # so just return something safe.
                return ['\\ ']
            if self.isLetter(unlexed[0]):
                return self.scanControlSequence(sofar + unlexed[0], unlexed[1:])
            else:
                word = sofar + unlexed[0]
                if self.isOK(word):
                    return [word] + self.doit(unlexed[1:])
                else:
                    return [self.forbid(word)] + self.doit(unlexed[1:])
        else:
            if len(unlexed) == 0:
                if self.isOK(sofar):
                    return [sofar]
                else:
                    return [self.forbid(sofar)]
            if self.isLetter(unlexed[0]):
                return self.scanControlSequence(sofar + unlexed[0], unlexed[1:])
            else:
                if self.isOK(sofar):
                    return [sofar] + self.doit(unlexed)
                else:
                    return [self.forbid(sofar)] + self.doit(unlexed)

    @classmethod
    def escape(self, sofar, unlexed):
        if len(unlexed) == 0:
            return [sofar]
        if self.isEscapeChar(unlexed[0]):
            return [sofar] + self.scanControlSequence(unlexed[0], unlexed[1:])
        return self.escape(sofar + unlexed[0], unlexed[1:])

    @classmethod
    def applies(self, work):
        # overapproximate
        return True

    @classmethod
    def doit(self, word):
        return self.escape('', word)

class EscapeEndEdnote(MicrotypeFeature):
    """
    Escpage the string \\end{ednote}, so that ednotes end
    where we expect them to end.
    """
    endednote = re.compile('\\\\end{ednote}')
    
    @classmethod
    def applies(self, word):
        if self.endednote.search(word) is not None:
            return True
        return  False

    @classmethod
    def doit(self, word):
        return self.endednote.sub('|end{ednote}', word)

def applyMicrotypefeatures(wordlist, featurelist):
    """
    sequentially apply (in the sense wordlist >>= feature)
    the features to the wordlist. Return the concatenation
    of the result.
    """
    for feature in featurelist:
        newwordlist = []
        for word in wordlist:
            if feature.applies(word):
                newwordlist.extend(feature.doit(word))
            else:
                newwordlist.append(word)
        wordlist = newwordlist
    return ''.join(wordlist)

def doMicrotype(text, features, separators):
    """
    Do micro typography with the given features and
    separators. Note that the order of the features
    matters!
    """
    result = ''
    word = ''
    for c in text:
        if not c in set(separators):
            word = word + c
        else:
            word = applyMicrotypefeatures([word], features)
            result = result + word +c
            word = ''
    word = applyMicrotypefeatures([word], features)
    result = result + word
    return result

def defaultMicrotype(text):
    
    features = [ThinSpaceAfterNumber, SplitSpaces, SplitEllipsis, Percent,
                Ampersand, Caret, Hashmark, Quote,
                StandardAbbreviations, FullStop, OpenQuotationMark,
                CloseQuotationMark, Acronym, NaturalNumbers, EscapeCommands]
    # FIXME '-' should not be a separator so we are able to detect dashes '--'
    #       however this will break NaturalNumbers for negative inputs
    separators = '\t,;()-' # no point, might be in abbreviations;
                           # spaces will be changed after numbers
    return doMicrotype(text, features, separators)

def mathMicrotype(text):
    # FIXME we want to substitute '...' -> '\dots{}' in math mode too
    features = [Percent, Hashmark, NaturalNumbers, EscapeCommands]
    separators = ''
    return doMicrotype(text, features, separators)

def ednoteMicrotype(text):
    features = [EscapeEndEdnote]
    separators = ''
    return doMicrotype(text, features, separators)

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

    def toTex(self):
        return defaultMicrotype(self.text)

    def toHtml(self):
        result = self.text
        result = re.sub('&', '&amp;', result)
        result = re.sub('<', '&lt;', result)
        result = re.sub('>', '&gt;', result)
        result = re.sub('"', '&#34;', result)
        result = re.sub("'", '&#39;', result)
        return result

    def toDF(self):
        return self.text

class PEmph(PTree):
    """
    An emphasized piece of text.
    """
    def __init__(self, text):
        self.text = text

    def debug(self):
        return ('emph', self.text)

    def toTex(self):
        return '\\emph{' + defaultMicrotype(self.text) + '}'

    def toHtml(self):
        return '<em>' + self.text + '</em>'

    def toDF(self):
        return '_' + self.text + '_'

class PMath(PTree):
    """
    An non-display math area.
    """
    def __init__(self, text):
        self.text = text

    def debug(self):
        return ('math', self.text)

    def toTex(self):
        return '$%1s$' % mathMicrotype(self.text)

    def toHtml(self):
        return '$%1s$' % self.text

    def toDF(self):
        return '$%1s$' % self.text

class PDisplayMath(PTree):
    """
    An display math area.
    """
    def __init__(self, text):
        self.text = text

    def debug(self):
        return ('displaymath', self.text)

    def toTex(self):
        return '$$%1s$$' % mathMicrotype(self.text)

    def toHtml(self):
        return "<div class=\"displaymath\">$$%1s$$</div>" % self.text

    def toDF(self):
        return '$$%1s$$' % self.text

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

    def toTex(self):
        return '\n\\begin{ednote}\n' + ednoteMicrotype(self.text) + '\n\\end{ednote}\n'

    def toHtml(self):
        result = self.text
        result = re.sub('&', '&amp;', result)
        result = re.sub('<', '&lt;', result)
        result = re.sub('>', '&gt;', result)
        return '\n<pre class="ednote">\n' + result + '\n</pre>\n'

    def toDF(self):
        # find a bracket combination not in the text
        openbracket = '{'
        closebracket = '}'
        while self.text.find(closebracket) >= 0:
            openbracket = openbracket + '{'
            closebracket = closebracket + '}'
        return '\n' + openbracket + '\n' + self.text + '\n' + closebracket + '\n'

class PParagraph(PTree):
    def __init__(self, subtree):
        self.it = subtree

    def debug(self):
        return ('Paragraph', self.it.debug())

    def isEmpty(self):
        return self.it.isEmpty()

    def toTex(self):
        return '\n' + self.it.toTex() + '\n'

    def toHtml(self):
        return '\n<p>\n'  + self.it.toHtml() + '\n</p>\n'

    def toDF(self):
        return '\n\n' + self.it.toDF() + '\n'


class PHeading(PTree):
    def __init__(self, title, level):
        self.title = title
        self.level = level

    def debug(self):
        return ('Heading', self.level, self.title)

    def toTex(self):
        result = '\n\\'
        for _ in range(self.level):
            result = result + 'sub'
        result = result + 'section'
        result = result + '{' + defaultMicrotype(self.title) + '}\n'
        return result

    def toHtml(self):
        return ('\n<h%d>' % (self.level +1)) + self.title + ('</h%d>\n' % (self.level +1))

    def toDF(self):
        result = '\n\n'
        for _ in range(self.level + 1):
            result = result + '['
        result = result + self.title
        for _ in range(self.level + 1):
            result = result + ']'
        return result

    def getLevel(self):
        return self.level

    def getTitle(self):
        return self.title


class PAuthor(PTree):
    def __init__(self, author):
        self.author = author

    def getAuthor(self):
        return self.author

    def debug(self):
        return ('Author', self.author)

    def toTex(self):
        return '\\authors{' + defaultMicrotype(self.author) + '}\n'

    def toHtml(self):
        return '<i>' + self.author + '</i>'

    def toDF(self):
        return '\n(' + self.author + ')'

class PDescription(PTree):
    def __init__(self, key, value):
        self.key = key
        self.value = value

    def debug(self):
        return ('Description', self.key.debug(), self.value.debug())

    def toTex(self):
        return '\n\\paragraph{' + self.key.toTex() + '} ' + self.value.toTex() + '\n'

    def toHtml(self):
        return '\n<p><b>' + self.key.toHtml() + '</b> ' + self.value.toHtml() + '\n</p>\n'

    def toDF(self):
        return '\n\n*%1s* %s' % (self.key.toDF(), self.value.toDF())

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
        result = '\n'
        for item in self.items:
            result = result + item.toDF()
        return result

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
            return '\n\\item ' + self.it.toTex()
        else:
            return '\n% ' + self.number + '\n\\item ' + self.it.toTex()
        

    def toHtml(self):
        return '\n<li> ' + self.it.toHtml()

    def toDF(self):
        if self.number is None:
            return '\n-' + self.it.toDF()
        else:
            return '\n' + self.number + '. ' + self.it.toDF()

class Chargroup:
    """
    Abstract class where all char-groups inherit from.

    A char group is a group of sucessive characters within
    a line group, forming a logical unit within that line
    group, like an emphasis, or a math environment.
    """
    def __init__(self, initial=None):
        self.text = ''
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
        return char == '_'

    def rejectcontinuation(self, char):
        if len(self.text) < 2:
            return False
        return self.text.endswith('_')

    def enforcecontinuation(self, char):
        ## Force to get the closing _
        if self.rejectcontinuation(char):
            return False
        return char == '_'

    def parse(self):
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
    def __init__(self, initial=None):
        self.trailingbackslashs = 0
        self.done = False
        self.count = 0
        Chargroup.__init__(self, initial=initial)

    @classmethod
    def startshere(self, char, lookahead=None):
        return char == '$' and not lookahead == '$'

    def append(self, chars):
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

    def enforcecontinuation(self, char):
        return not self.done

    def rejectcontinuation(self, char):
        return self.done

    def parse(self):
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
    def __init__(self, initial=None):
        self.done = False
        self.trailingbackslashs = 0
        self.trailingdollar = 0
        self.count = 0
        Chargroup.__init__(self, initial=initial)

    @classmethod
    def startshere(self, char, lookahead=None):
        return char == '$' and lookahead == '$'

    def append(self, chars):
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
                
    def enforcecontinuation(self, char):
        return not self.done

    def rejectcontinuation(self, char):
        return self.done

    def parse(self):
        result = self.text
        if result.startswith('$$'):
            result = result[2:]
        if result.endswith('$$'):
            result = result[:-2]
        if result.endswith('$'):
            result = result + ' '
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

def splitrightbracket(line):
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


def isMirrorBracket(firstline, lastline):
    """
    Return True iff lastline ends with the matching
    bigbracket to the one the firstline starts with.
    """
    closing = { '{' : '}', '(' : ')', '<' : '>', '[' : ']' }

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
        return line.startswith('{')

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
            start = start + '\n'
        end = splitrightbracket(self.lines[-1])[0]

        if len(self.lines) > 2 and len(end) != 0:
            end = '\n' + end

        return PEdnote(start + '\n'.join(self.lines[1:-1]) + end)


class Heading(Linegroup):
    """
    Headings, marked [As such] in dokuforge
    """
    def __init__(self):
        Linegroup.__init__(self)

    @classmethod
    def startshere(self, line, after=None):
        return line.startswith('[') and not line.startswith('[[')

    def enforcecontinuation(self, line):
        if isemptyline(line):
            return False
        if len(self.lines) < 1:
            return True
        return ']' not in set(self.lines[-1])

    def rejectcontinuation(self, line):
        return not self.enforcecontinuation(line)

    def getTitle(self):
        title = ' '.join(self.lines)
        while title.startswith('['):
            title = title[1:]
        while title.endswith((' ', '\t')):
            title = title[:-1]
        while title.endswith(']'):
            title = title[:-1]
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
        return line.startswith('[[') and not line.startswith('[[[')

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
        return line.startswith('(') and isinstance(after, Heading)

    def enforcecontinuation(self, line):
        if isemptyline(line):
            return False
        if len(self.lines) < 1:
            return True
        return ')' not in set(self.lines[-1])

    def rejectcontinuation(self, line):
        return not self.enforcecontinuation(line)

    def parse(self):
        author = ' '.join(self.lines)
        while author.startswith('('):
            author = author[1:]
        while author.endswith((' ', '\t')):
            author = author[:-1]
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
    def __init__(self):
        Linegroup.__init__(self)
    
    @classmethod
    def startshere(self, line, after=None):
        return line.startswith('- ')

    def parse(self):
        if len(self.lines) < 1:
            return PItem(defaultInnerParse(self.lines))
        firstline = self.lines[0]
        if firstline.startswith('-'):
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
        return line.startswith('*')

    def parse(self):
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
    groups = grouplines(text.splitlines(), dffeatures)
    ptrees = [g.parse() for g in groups]
    ptrees = groupItems(ptrees)
    ptrees = removeEmpty(ptrees)
    return PSequence(ptrees)

def dfOverview(text):
    groups = grouplines(text.splitlines(), dffeatures)
    headings = [g for g in groups if isinstance(g, Heading)]
    return [g.parse() for g in headings]
