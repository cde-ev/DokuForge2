import os.path

from werkzeug.wsgi import SharedDataMiddleware

from dokuforge.application import Application
from dokuforge.storage import Storage
from dokuforge.user import UserDB

def buildapp(workdir="./work/", dfdir="./df/", sessiondbpath=":memory:",
             staticservepath="/static/"):
    """
    @param sessiondbpath: path to a sqlite3 database dedicated to storing
        session cookies. Unless a forking server is used ":memory:" is fine.
    @param workdir: path to directory containing configuration files
    @param dfdir: path to directory storing all the documentation projects.
        Each directory within this directory represents one academy.
    """
    userdb = UserDB(Storage(workdir, "userdb"))
    userdb.load()
    groupstore = Storage(workdir, "groupdb")
    app = Application(userdb, groupstore, dfdir, staticservepath, sessiondbpath)
    app = SharedDataMiddleware(app,
        {staticservepath: os.path.join(os.path.dirname(__file__), "static")})
    return app
