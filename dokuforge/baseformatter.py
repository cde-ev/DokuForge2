from dokuforge.parser import ParseLeaf

class BaseFormatter:
    """
    Base class for transforming the tree representation of the Parser into
    the desired output format.

    It takes the tree and recursively formats the entries.
    """
    handle_heading = u"[%s]".__mod__
    handle_subheading = u"[[%s]]".__mod__
    handle_ednote = u"{%s}".__mod__
    handle_displaymath = u"$$%1s$$".__mod__
    handle_authors = u"(%s)".__mod__
    handle_paragraph = u"%s".__mod__
    handle_list = u"%s".__mod__
    handle_item = u"- %s".__mod__
    handle_emphasis = u"_%s_".__mod__
    handle_keyword = u"*%s*".__mod__
    handle_inlinemath = u"$%1s$".__mod__
    handle_nestedednote = u"{%s}".__mod__
    handle_Dollar = u"%.0s\\$".__mod__

    escapemap = {}

    escapeexceptions = []

    def __init__(self, tree):
        self.tree = tree

    def generateoutput(self, tree=None, escape=True):
        """
        Take the tree (self.tree if not given) and generate an output string.

        This uses the handle_* methods to recursively transform the
        tree. The escaping is done with escapemap and controlled by
        escapeexceptions.

        @param tree: tree to transform, self.tree if none is given
        @type tree: ParseTree or ParseLeaf
        @param escape: toggle escaping of all ParseLeaf data
        @type escape: bool
        """
        if tree is None:
            tree = self.tree
        if isinstance(tree, ParseLeaf):
            data = tree.data
            try:
                handler = getattr(self, "handle_%s" % tree.ident)
            except AttributeError:
                pass
            else:
                data = handler(data)
            if escape:
                return data.translate(self.escapemap)
            return data
        output = u""
        if tree.ident in self.escapeexceptions:
            escape=False
        for x in tree.tree:
            value = self.generateoutput(x, escape)
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        return output
