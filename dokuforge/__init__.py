from werkzeug.wsgi import SharedDataMiddleware

from dokuforge.application import Application
from dokuforge.storage import Storage
from dokuforge.user import UserDB

def buildapp(workdir="work", dfdir="./df/", templatedir="./templates/",
             styledir="./style/", sessiondbpath=":memory:",
             staticdir="./static"):
    """
    @fixme: describe workdir, dfdir styledir
    @param templatedir: path to the jinja2 templates used by dokuforge
    @param sessiondbpath: path to a sqlite3 database dedicated to storing
        session cookies. Unless a forking server is used ":memory:" is fine.
    @param staticdir: path to the static files used by dokuforge. This includes
        style files and images.
    """
    userdb = UserDB(Storage(workdir, "userdb"))
    userdb.load()
    groupstore = Storage(workdir, "groupdb")
    app = Application(userdb, groupstore, dfdir, templatedir, styledir,
                      sessiondbpath)
    app = SharedDataMiddleware(app, {"/static": staticdir})
    return app
