from werkzeug.wsgi import SharedDataMiddleware

from dokuforge.application import Application
from dokuforge.storage import Storage
from dokuforge.user import UserDB

def buildapp(workdir="./work/", dfdir="./df/", templatedir="./templates/",
             styledir="./style/", sessiondbpath=":memory:",
             staticdir="./static/", staticservepath="/static/"):
    """
    @param templatedir: path to the jinja2 templates used by dokuforge
    @param sessiondbpath: path to a sqlite3 database dedicated to storing
        session cookies. Unless a forking server is used ":memory:" is fine.
    @param staticdir: path to the static files used by dokuforge. This includes
        style files and images.
    @param workdir: path to directory containing configuration files
    @param dfdir: path to directory storing all the documentation projects.
        Each directory within this directory represents one academy.
    @param styledir: path to directory containing the content of the style
        guide. This path is realtive to the templatedir.
    """
    userdb = UserDB(Storage(workdir, "userdb"))
    userdb.load()
    groupstore = Storage(workdir, "groupdb")
    app = Application(userdb, groupstore, dfdir, templatedir, styledir,
                      staticservepath, sessiondbpath)
    app = SharedDataMiddleware(app, {staticservepath: staticdir})
    return app
