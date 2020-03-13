import os.path

try:
    from werkzeug.wsgi import SharedDataMiddleware
except ImportError:
    # moved with werkzeug-1.0.0
    from werkzeug.middleware.shared_data import SharedDataMiddleware

from dokuforge.application import Application
from dokuforge.paths import PathConfig

def buildapp(pathconfig=PathConfig()):
    """
    @type pathconfig: PathConfig
    """
    app = Application(pathconfig)
    app = SharedDataMiddleware(
        app, {"/%s" % pathconfig.staticservepath:
              os.path.join(os.path.dirname(__file__), "static")})
    return app
