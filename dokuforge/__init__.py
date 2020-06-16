import os.path

from werkzeug.middleware.shared_data import SharedDataMiddleware

from dokuforge.application import Application
from dokuforge.paths import PathConfig


def buildapp(pathconfig: PathConfig = PathConfig()):
    app = Application(pathconfig)
    app = SharedDataMiddleware(
        app, {"/%s" % pathconfig.staticservepath:
              os.path.join(os.path.dirname(__file__), "static")})
    return app
