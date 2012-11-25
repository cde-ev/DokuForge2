from werkzeug import exceptions
import werkzeug.routing


class DfException(Exception):
    """
    Cover class for all exceptions introduced by Dokuforge.
    Whenever a non-DfException is thrown outside a module,
    this indicates a programming error.
    """
    pass


class CheckError(StandardError, DfException):
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


class MalformedAdress(exceptions.NotFound, DfException):
    """
    The class of exceptions to be thrown if and when the
    user asks for an invalid adress.

    This kind of exceptions should also fly up to the werkzeug
    level.
    """
    pass

class NotEnoughPriveleges(exceptions.Forbidden, DfException):
    """
    The class of exceptions to be thrown if and when the
    user asks for something he is not allowed to see/do.

    This kind of exceptions should also fly up to the werkzeug
    level.
    """
    pass

class MalformedPOSTRequest(exceptions.BadRequest, DfException):
    """
    The class of exceptions to be thrown if and when the user provides
    invlaid input for a POST request, that cannot occur by just using a
    browser. In other words, the user hand-crafted a request.

    This kind of exceptions should also fly up to the werkzeug
    level.
    """
    pass

class RcsUserInputError(MalformedPOSTRequest):
    """
    The class of exceptions to be thrown if an when the
    user provides invalid specifications of rcs input (mainly
    version numbers).
    """
    pass

class PageOutOfBound(MalformedAdress):
    """
    The class of exceptions to be thrown if and when a request
    refers to a non-existing page.
    """
    pass

class PageIndexOutOfBound(MalformedAdress):
    """
    The class of exceptions to be thrown if and when a request
    refers to a non-existing page index.
    """
    pass

class BlobOutOfBound(MalformedAdress):
    """
    The class of exceptions to be thrown if and when a request
    refers to a non-existing page.
    """
    pass

class TemporaryRequestRedirect(exceptions.HTTPException,
                               werkzeug.routing.RoutingException):
    """
    The class of exceptions to raise when the user is not logged in and
    tried to acces something were he needs to be authenticated.
    """
    code = 307

    def __init__(self, new_url):
        werkzeug.routing.RoutingException.__init__(self, new_url)
        self.new_url = new_url

    def get_response(self, environ):
        return werkzeug.utils.redirect(self.new_url, self.code)

class StorageFailure(DfException):
    """
    A StorageFailure does not occur under normal circumstances. It can be
    thought of as an AssertionError, except that you cannot suppress it with -O.
    It may be raised when the disk is full or when dokuforge is lacking
    permission to access its own files for example.
    """
    def __init__(self, msg):
        """
        @type msg: str
        """
        self.msg = msg

    def __str__(self):
        return self.msg

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name, self.msg)

class RcsError(StorageFailure):
    """A failure from a spawned rcs command."""
    def __init__(self, msg, stderr, code):
        """
        @type msg: str
        @type stderr: bytes
        @param stderr: the contents of stderr of a called provides being
                responsible for this exception if any
        @type code: int
        @param code: the exit status of a called process being responsible for
                this exception if any
        """
        StorageFailure.__init__(self, msg)
        self.stderr = stderr
        self.code = code
    def __repr__(self):
        if self.code:
            return "%s(%r, %r, %d)" % (self.__class__.__name__, self.msg,
                                       self.stderr, self.code)
        if self.stderr:
            return "%s(%r, %r)" % (self.__class__.__name__, self.msg,
                                   self.stderr)
        return "%s(%r)" % (self.__class__.__name__, self.msg)
