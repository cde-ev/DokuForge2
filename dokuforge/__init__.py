import os.path

try:
    from werkzeug.middleware.shared_data import SharedDataMiddleware
except ImportError:
    # previous location for <werkzeug-1.0.0
    from werkzeug.wsgi import SharedDataMiddleware

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
