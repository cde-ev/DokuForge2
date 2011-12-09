from werkzeug import exceptions
import werkzeug.routing


class DfException():
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

class FileDoesNotExist(CheckError):
    pass

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

