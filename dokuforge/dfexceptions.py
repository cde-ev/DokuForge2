from werkzeug import exceptions

class DfException():
    """
    Cover class for all exceptions introduced by Dokuforge.
    Whenever a non-DfException is thrown outside a module,
    this indicates a programming error.
    """
    pass


class CheckError(StandardError,DfException):
    def __init__(self, msg, exp):
        StandardError.__init__(self, msg)
        assert isinstance(msg, unicode)
        assert isinstance(exp, unicode)
        self.message = msg
        self.explanation = exp
    def __str__(self):
        return self.message


class InvalidBlobFilename(CheckError):
    pass

## Note: exceptions.Conflict serves as a placeholder for
##       the http-error code we will finally choose; this
##       is still in discussion by Helmut and Markus
class MalformedUserInput(exceptions.Conflict,DfException):
    """
    The class of exceptions to be thrown if and when the
    user provides invlaid input, that cannot occur by just
    using a browser. In other words, the user hand-crafted
    a request.
    
    This kind of exceptions should also fly up to the werkzeug
    level.
    """
    def __init__(self,*args,**kwargs):
        exceptions.Conflict.__init__(self,*args, **kwargs)

class RcsUserInputError(CheckError, MalformedUserInput):
    """
    The class of exceptions to be thrown if an when the
    user provides invalid specifications of rcs input (mainly
    version numbers).
    """
    def __init__(self, msg, exp):
        CheckError.__init__(self,msg,exp)
        MalformedUserInput.__init__(self)

class PageOutOfBound(MalformedUserInput):
    """
    The class of exceptions to be thrown if and when a request
    refers to a non-existing page.
    """
    def __init__(self, *args, **kvargs):
        MalformedUserInput.__init__(self, *args, **kvargs)

class PageIndexOutOfBound(MalformedUserInput):
    """
    The class of exceptions to be thrown if and when a request
    refers to a non-existing page index.
    """
    def __init__(self, *args, **kvargs):
        MalformedUserInput.__init__(self, *args, **kvargs)

class BlobOutOfBound(MalformedUserInput):
    """
    The class of exceptions to be thrown if and when a request
    refers to a non-existing page.
    """
    def __init__(self, *args, **kvargs):
        MalformedUserInput.__init__(self, *args, **kvargs)

