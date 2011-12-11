# -*- coding: utf-8 -*-

from dokuforge.baseformatter import BaseFormatter
from dokuforge.parser import ParseLeaf

## list of useful math commands mostly taken from 'A Guide To LaTeX' by Kopka
whitelist = [##
## greek letters
u"alpha", u"beta", u"gamma", u"delta", u"epsilon", u"zeta", u"eta",
u"theta", u"iota", u"kappa", u"lambda", u"mu", u"nu", u"xi", u"pi", u"rho",
u"sigma", u"tau", u"upsilon", u"phi", u"chi", u"psi", u"omega", u"Gamma",
u"Delta", u"Theta", u"Lambda", u"Xi", u"Pi", u"Sigma", u"Phi", u"Psi",
u"Omega", u"varepsilon", u"vartheta", u"varpi", u"varrho", u"varsigma",
u"varphi",
## environments
u"begin", u"end",
## math layout
u"frac", u"sqrt", u"sum", u"int", u"ldots", u"cdots", u"vdots", u"ddots",
u"oint", u"prod", u"coprod"
## math symbols
u"pm", u"cap", u"circ", u"bigcirc" u"mp", u"cup", u"bullet", u"Box"
u"times", u"uplus", u"diamond", u"Diamond", u"div", u"sqcap",
u"bigtriangleup", u"cdot", u"sqcup", u"bigtriangledown", u"ast", u"vee",
u"unlhd", u"triangleleft", u"star", u"wedge", u"unrhd", u"triangleright",
u"dagger", u"oplus", u"oslash", u"setminus", u"ddagger", u"ominus", u"odot",
u"wr", u"amalg", u"otimes",
## math relations
u"le", u"leq", u"ge", u"geq", u"neq", u"sim", u"ll", u"gg", u"doteq",
u"simeq", u"subset", u"supset", u"approx", u"asymp", u"subseteq",
u"supseteq", u"cong", u"smile", u"sqsubset", u"sqsupset", u"equiv",
u"frown", u"sqsubseteq", u"sqsupseteq", u"propto", u"bowtie", u"in", u"ni",
u"prec", u"succ", u"vdash", u"dashv", u"preceq", u"succeq", u"models",
u"perp", u"parallel", u"mid",
## negations
u"not", u"notin",
## arrows
u"leftarrow", u"gets", u"longleftarrow", u"uparrow", u"Leftarrow",
u"Longleftarrow", u"Uparrow", u"rightarrow", u"to", u"longrightarrow",
u"downarrow", u"Rightarrow", u"Longrightarrow", u"Downarrow",
u"leftrightarrow", u"longleftrightarrow", u"updownarrow", u"Leftrightarrow",
u"Longleftrightarrow", u"Updownarrow", u"mapsto", u"longmapsto", u"nearrow",
u"hookleftarrow", u"hookrightarrow", u"searrow", u"leftharpoonup",
u"rightharpoonup", u"swarrow", u"leftharpoondown", u"rightharpoondown",
u"nwarrow", u"rightleftharpoons", u"leadsto",
## various symbols
u"aleph", u"prime", u"forall", u"hbar", u"emptyset", u"exists", u"imath",
u"nablaa", u"neg", u"triangle", u"jmath", u"surd", u"flat", u"clubsuit",
u"ell", u"partial", u"natural", u"diamondsuit", u"wp", u"top", u"sharp",
u"heartsuit", u"Re", u"bot", u"spadesuit", u"Im", u"vdash", u"angle",
u"Join", u"mho", u"dashv", u"backslash", u"infty",
## big symbols
u"bigcap", u"bigodot", u"bigcup", u"bigotimes", u"bigsqcup", u"bigoplus",
u"bigvee", u"biguplus", u"bigwedge",
## function names
u"arccos", u"cosh", u"det", u"inf" u"limsup", u"Pr", u"tan", u"arcsin",
u"cot", u"dim", u"ker", u"ln", u"sec", u"tanh", u"arctan", u"coth", u"exp",
u"lg", u"log", u"sin", u"arg", u"csc", u"gcd", u"lim", u"max", u"sinh",
u"cos", u"deg", u"hom", u"liminf", u"min", u"sup",
## accents
u"hat", u"breve", u"grave", u"bar", u"check", u"acute", u"ti1de", u"vec",
u"dot", u"ddot", u"mathring",
## parens
u"left", u"right", u"lfloor", u"rfloor", u"lceil", u"rceil", u"langle",
u"rangle",
## misc
u"stackrel", u"binom"
]

## abbreviations taken from the style guide
abbreviations = [[u"z", u"B"], [u"d", u"h"], [u"u", u"a"], [u"s", u"o"],
[u"s", u"u"], [u"ca"], [u"etc"], [u"bzw"], [u"vgl"], [u"sog"], [u"o", u"Ä"],
[u"v", u"Chr"], [u"n", u"Chr"], [u"f"], [u"ff"]]


## list of units, mostly taken from Wikipedia
siprefix = [u"", u"k", u"m", u"μ", u"M", u"n", u"G"]
units = [##
## base units
u"A", u"mol", u"K", u"m", u"s", u"g", u"cd",
## derived units
u"Hz", u"rad", u"sr", u"N", u"Pa", u"J", u"W", u"C", u"V", u"F", u"Ω", u"S",
u"Wb", u"T", u"H", u"lm", u"lx", u"Bq", u"Gy", u"Sv", u"kat",
## common products
u"Wh", u"Ws", u"Nm",
## other units officially accepted by SI
u"min", u"h", u"d", u"°", u"ha", u"l", u"L", u"t", u"Np", u"B", u"dB",
u"eV", u"u", u"ua", u"e", u"bar", u"atm", u"psi", u"Torr",
## misc
u"TL"]

class Context:
    """
    Class for storing context information for exporter.

    This class stores the information, where in the ParseTree we are and
    what is around us. It also provides several methods to extract
    information about the surounding.
    """
    def __init__(self, leaf, neighbours, environ):
        """
        @param leaf: current object which is processed
        @type leaf: ParseTree or ParseLeaf
        @param neighbours: list of all nodes adjacent to leaf, leaf is in this
            list
        @type neighbours: [ParseTree or ParseLeaf]
        @param environ: list of all idents from 'root' to the parent of leaf
        @type environ: [str]
        """
        self.leaf = leaf
        self.neighbours = neighbours
        self.environ = environ
        self.index = neighbours.index(leaf)


    def inenviron(self, query):
        """
        Checks whether we are currently inside a ParseTree of type query.

        @type query: str
        @rtype: bool
        """
        for x in query:
            if x in self.environ:
                return True
        return False


    def lookleafdata(self, n=1):
        """
        @param n: offset from our current position
        @type n: int
        @rtype: unicode or None
        @returns: the data of the Leaf n steps ahead of the current position
            or None if this does not exist or is not a ParseLeaf
        """
        try:
            if not isinstance(self.neighbours[self.index+n], ParseLeaf):
                return None
            return self.neighbours[self.index+n].data
        except IndexError:
            return None

    def lookleaftype(self, n=1):
        """
        @param n: offset from our current position
        @type n: int
        @rtype: str or None
        @returns: the type of the Leaf n steps ahead of the current position
            or None if this does not exist or is not a ParseLeaf
        """
        try:
            if not isinstance(self.neighbours[self.index+n], ParseLeaf):
                return None
            return self.neighbours[self.index+n].ident
        except IndexError:
            return None

    def comparedata(self, data):
        """
        Checks whether the next nodes contain the specified data

        @param data: pattern to check for
        @type data: [unicode]
        @rtype: bool
        """
        for i in range(len(data)):
            if not self.lookleafdata(i+1) == data[i]:
                return False
        return True

    def checkabbrev(self, abbrev):
        """
        Check wheter at the current position starts the abbreviation abbrev.

        @type abbrev: [unicode]
        @rtype: bool
        """
        pos = 0
        for x in abbrev:
            if not self.lookleafdata(pos) == x and \
                self.lookleafdata(pos + 1) == u'.':
                return False
            pos += 2
            if self.lookleaftype(pos) == "Whitespace":
                pos += 1
        return True

    def countabbrev(self, abbrev):
        """
        Count the nodes occupied by the abbreviation abbrev at the current
        position. The caller has to ensure, that the abbreviation abbrev
        actually starts at the current position.

        This is not a trivial operation, since we tolerate some whitespace
        in abbreviations which has to be counted.

        @type abbrev: [unicode]
        @rtype: int
        """
        pos = 0
        for x in abbrev:
            if not self.lookleafdata(pos) == x and \
                self.lookleafdata(pos + 1) == u'.':
                return 0
            pos += 2
            if self.lookleaftype(pos) == "Whitespace":
                pos += 1
        return pos

    def scanfordash(self, pos=3):
        """
        Search for a dash in the current sentence. This is important to get
        the difference between 'a --~nice~-- word' and 'check~-- so you win'
        right.

        @type pos: int
        @param pos: offset from current position to start from
        @rtype: bool
        """
        if self.lookleafdata(pos) == u'.' or \
            self.lookleafdata(pos + 1) == u'.' or \
            self.lookleafdata(pos + 2) == u'.':
            return False
        while not self.lookleafdata(pos + 2) == u'.':
            if self.lookleaftype(pos) == "Whitespace" and \
                self.lookleafdata(pos + 1) == u'-' and \
                self.lookleafdata(pos + 2) == u'-':
                return True
            pos += 1
        return False

    def checkunit(self, pos=1):
        """
        Check wheter there is a unit at offset pos.

        @type pos: int
        @param pos: offset from current position to start from
        """
        tocheck = self.lookleafdata(pos)
        for x in siprefix:
            for y in units:
                if tocheck == x+y:
                    return True
        return False


class TeXFormatter(BaseFormatter):
    """
    Formatter for converting the tree representation into TeX for export.
    """
    ## escaping is done by the advanced_handle_* routines
    ## they take care of '\' and '%'

    handle_heading = u"\\section{%s}".__mod__
    handle_subheading = u"\\subsection{%s}".__mod__
    handle_ednote = u"\\begin{ednote}%s\\end{ednote}".__mod__
    handle_displaymath = u"\\[%s\\]".__mod__
    handle_authors = u"\\authors{%s}".__mod__
    handle_paragraph = "%s".__mod__
    handle_emphasis = u"\\emph{%s}".__mod__
    handle_keyword = u"\\textbf{%s}".__mod__
    # inherit handle_inlinemath
    handle_list = u"\\begin{itemize}\n%s\n\end{itemize}".__mod__
    handle_item = u"\\item %s".__mod__
    handle_Dollar = u"%.0s\\$".__mod__


    def __init__(self, tree):
        """
        @type tree: ParseTree
        """
        BaseFormatter.__init__(self, tree)
        self.dashesseen = 0
        self.quotesseen = 0

    def handle_nestedednote(self, data):
        """
        Do not allow '{ednote}' inside ednotes to prevent '\end{ednote}'.

        @type data: unicode
        """
        if data == u"ednote":
            return u"{\\@forbidden ednote}"
        else:
            return "{%s}" % data

    def advanced_handle_Backslash(self, leaf, context):
        """
        Handling of backslashs is particularly delicate since we want to allow
        only a limited set of actions.

        @type leaf: ParseLeaf
        @type context: Context
        """
        if context.inenviron(["inlinemath", "displaymath"]) and \
            context.lookleafdata() in whitelist:
            return (u'\\' + context.lookleafdata(), 1)
        elif context.inenviron(["inlinemath", "displaymath"]) and \
            context.lookleaftype() == "Backslash":
            if context.lookleaftype(2) == "Newline":
                return (u'\\\\', 1)
            else:
                return (u'\\\\\n', 1)
        else:
            if context.lookleaftype() == "Backslash":
                return (u'\\@\\forbidden\\newline ', 1)
            elif context.lookleaftype() == "Word":
                return (u'\\@\\forbidden\\', 0)
            else:
                return (u'\\@\\forbidden\\ ', 0)

    def advanced_handle_Word(self, leaf, context):
        """
        @type leaf: ParseLeaf
        @type context: Context
        """
        ## search for abbreviations
        if context.lookleafdata() == u'.' and \
            not context.inenviron(["inlinemath", "displaymath"]):
            for abbrev in abbreviations:
                if context.checkabbrev(abbrev):
                    return(u'\\@' + u'.\\,'.join(abbrev) + u'.',
                           context.countabbrev(abbrev))
        ## search for acronyms
        if leaf.data.isupper() and len(leaf.data) > 1:
            return (u'\\@\\acronym{%s}' % leaf.data, 0)
        else:
            return (leaf.data, 0)

    def advanced_handle_Newpar(self, leaf, context):
        """
        @type leaf: ParseLeaf
        @type context: Context
        """
        ## reset quotes at end of paragraph
        self.quotesseen = 0
        return (u'\n\n', 0)

    def advanced_handle_Token(self, leaf, context):
        """
        @type leaf: ParseLeaf
        @type context: Context
        """
        ## inside ednotes no post-processing is done
        if context.inenviron(["ednote", "nestedednote"]):
            return (leaf.data, 0)
        ## search for ellipses
        ## if no ellipse, a sentence just ended
        elif leaf.data == u'.':
            if context.comparedata([u'.', u'.']):
                return (u'\\@\\ldots{}', 2)
            else:
                ## reset number of seen dashes at every full stop
                self.dashesseen = 0
                return (u'.', 0)
        ## search for dashes --
        ## this is a bit tricky, since we have dashes for ranges 6--9 and
        ## dashes as delimiters in two forms ' --~a~-- ' and 'b~-- '
        elif leaf.data == u'-':
            if context.lookleafdata() == u'-':
                if not context.lookleaftype(2) == "Number":
                    if context.lookleaftype(2) == "Whitespace":
                        self.dashesseen += 1
                        ## == 1 since we allready increased dashesseen
                        if self.dashesseen % 2 == 1:
                            return (u'\\@--~', 2)
                        else:
                            return (u'\\@~-- ', 2)
                    else:
                        return (u'\\@--', 1)
                else:
                    return (u'--', 1)
            else:
                return (u'-', 0)
        ## escape %
        elif leaf.data == u'%':
            return (u'\\%', 0)
        ## ' is not processed further, but should only be used were
        ## appropriate (especially not as substitute for ")
        elif leaf.data == u"'":
            if not context.inenviron(["inlinemath" ,"displaymath"]):
                return (u"\\@'", 0)
            else:
                return (u"'", 0)
        ## prevent '^^'
        elif leaf.data == u'^':
            skips = 0
            while context.lookleafdata(skips+1) == u'^':
                skips += 1
            return (u'^', skips)
        ## handle quotes, there ar left and right ones
        ## this is locale to each paragraph, so an error does not wreck
        ## havoc for a whole part
        elif leaf.data == u'"':
            self.quotesseen += 1
            ## == 1 since we allready increased quotesseen
            if self.quotesseen % 2 == 1:
                ## left quote
                return (u'"`', 0)
            else:
                ## right quote
                return (u"\"'", 0)
        else:
            return (leaf.data, 0)

    def advanced_handle_Number(self, leaf, context):
        """
        @type leaf: ParseLeaf
        @type context: Context
        """
        number = u''
        ## format number if it's long enough
        if len(leaf.data) < 5:
            number = leaf.data
        else:
            rem = len(leaf.data) % 3
            if rem > 0:
                number = leaf.data[0:rem] + u'\\,'
            pos = 0
            while 3*(pos+1) + rem <= len(leaf.data):
                number += leaf.data[3*pos+rem:3*(pos+1)+rem] + u'\\,'
                pos +=1
            number = number[:-2]
        ## '3. ' is always output as '3.\,'
        if context.lookleafdata() == u'.' and \
            context.lookleaftype(2) == "Whitespace":
            return (number + u'.\\@\\,', 2)
        skip = 0
        ## tolerate whitespace ere ...
        if context.lookleaftype() == "Whitespace":
            skip = 1
        ## we check for units and ...
        if context.checkunit(1+skip):
            return (number + u'\\@\\,' + context.lookleafdata(skip+1), skip+1)
        ## percentage signs
        if context.lookleafdata(1+skip) == u'%':
            return (number + u'\\@\\,\\%', skip+1)
        return (number, 0)

    def advanced_handle_Whitespace(self, leaf, context):
        """
        Some whitespace turns into protected whitespace (~).

        @type leaf: ParseLeaf
        @type context: Context
        """
        ## dashes
        if context.comparedata([u'-', u'-']):
            if self.dashesseen % 2 == 1 or not context.scanfordash():
                self.dashesseen += 1
                return (u'\\@~--', 2)
            else:
                return (u' ', 0)
        ## ellipses
        elif context.comparedata([u'.', u'.', u'.']):
            return (u'\\@~\\ldots{}', 3)
        else:
            return (u' ', 0)


    def generateoutput(self):
        """
        Take self.tree and generate an output string.

        This method adds all the bells and whistles the exporter has. It
        mainly calls supergenerateoutput. There do not have to be many
        specials here, since the root ParseTree may only contain paragraph,
        heading, subheading, authors, displaymath, list, ednote, Newline and
        Newpar.
        """
        output = u""
        for x in self.tree.tree:
            assert x.ident in ("paragraph", "heading", "subheading", "authors",
                               "displaymath", "list", "ednote", "Newpar",
                               "Newline")
            value, _ = self.advancedgenerateoutput(x, Context(x, self.tree.tree,
                                                              ["root"]))
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        return output

    def advancedgenerateoutput(self, tree, context):
        """
        Take tree and recursively generate an output string.

        This method uses handle_* and advanced_handle_* methods to generate
        the output. advanced_handle_* methods are only available for leaves.
        """
        if isinstance(tree, ParseLeaf):
            data = tree.data
            skips = 0
            handler = None
            ## first try advanced handler
            try:
                handler = getattr(self, "advanced_handle_%s" % tree.ident)
            except AttributeError:
                pass
            else:
                data, skips = handler(tree, context)
            if handler is None:
                ## if no advanced handler, try normal handler
                try:
                    handler = getattr(self, "handle_%s" % tree.ident)
                except AttributeError:
                    pass
                else:
                    data = handler(data)
            return (data, skips)
        ## now we have a ParseTree
        output = u""
        skips = 0
        ## update environ
        context.environ.append(tree.ident)
        for x in tree.tree:
            ## skip nodes, allready processed earlier in the loop
            if skips > 0:
                skips -= 1
                continue
            value, skips = self.advancedgenerateoutput(x, Context(x, tree.tree,
                                                                  context.environ))
            ## no advanced_handle_* methods for non-leaves
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        ## update environ
        context.environ.pop()
        return (output, 0)
