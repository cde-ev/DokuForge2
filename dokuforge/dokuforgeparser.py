from dokuforge.treeparser import TreeParser, ParseLeaf


class DokuforgeToDokuforgeParser:
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

    def __init__(self, tree):
        self.output = u""
        self.tree = tree

    def generateoutput(self, tree=None):
        root = False
        if tree is None:
            tree = self.tree
            root = True
        if isinstance(tree, ParseLeaf):
            return tree.data
        output = u""
        for x in tree.tree:
            value = self.generateoutput(x)
            try:
                handler = getattr(self, "handle_%s" % x.ident)
            except AttributeError:
                pass
            else:
                value = handler(value)
            output += value
        if root:
            self.output = output
        return output

