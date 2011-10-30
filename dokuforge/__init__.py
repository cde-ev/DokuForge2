import os.path

from werkzeug.wsgi import SharedDataMiddleware

from dokuforge.application import Application
from dokuforge.paths import PathConfig

def buildapp(pathconfig=PathConfig()):
    """
    @type pathconfig: PathConfig
    """
    app = Application(pathconfig)
    app = SharedDataMiddleware(
        app, {pathconfig.staticservepath:
              os.path.join(os.path.dirname(__file__), "static")})
    return app
