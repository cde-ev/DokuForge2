#!/usr/bin/env python

import jinja2
import random
import os
import sqlite3
import copy
import re
import urllib
import werkzeug.utils
from werkzeug.wrappers import Request, Response
import werkzeug.routing
import wsgiref.util
import operator
from wsgitools.applications import StaticFile
from wsgitools.middlewares import TracebackMiddleware, SubdirMiddleware
from wsgitools.scgi.asynchronous import SCGIServer
# import other parts of Dokuforge
import academy
import course
import storage
import user

sysrand = random.SystemRandom()

def gensid(bits=64):
    """
    @type bits: int
    @param bits: randomness in bits of the resulting string
    @rtype: str
    @returns: a random string
    """
    return "%x" % random.getrandbits(bits)

class SessionHandler:
    """Associate users with session ids in a DBAPI2 database."""
    create_table = "CREATE TABLE IF NOT EXISTS sessions " + \
                   "(sid TEXT, user TEXT, UNIQUE(sid));"
    cookie_name = "sid"

    def __init__(self, db, request, response):
        """
        @param db: a DBAPI2 database that has a sessions table as described
                in the create_table class variable
        @type environ: dict
        """
        self.db = db
        self.cur = db.cursor()
        self.response = response
        self.sid = request.cookies.get(self.cookie_name)

    def get(self):
        """Find a user session.
        @rtype: str or None
        @returns: a username or None
        """
        if self.sid is None:
            return None
        self.cur.execute("SELECT user FROM sessions WHERE sid = ?;",
                         (self.sid.decode("utf8"),))
        results = self.cur.fetchall()
        if len(results) != 1:
            return None
        return results[0][0].encode("utf8")

    def set(self, username):
        """Initiate a user session.
        @type username: str
        """
        if self.sid is None:
            self.sid = gensid()
            self.response.set_cookie(self.cookie_name, self.sid)
        self.cur.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?);",
                         (self.sid.decode("utf8"), username.decode("utf8")))
        self.db.commit()

    def delete(self):
        """Delete a user session.
        @rtype: [(str, str)]
        @returns: a list of headers to be sent with the http response
        """
        if self.sid is not None:
            self.cur.execute("DELETE FROM sessions WHERE sid = ?;",
                             (self.sid.decode("utf8"),))
            self.db.commit()
            self.response.delete_cookie(self.cookie_name)

class RequestState:
    def __init__(self, request, sessiondb, userdb):
        self.request = request
        self.response = Response()
        self.sessionhandler = SessionHandler(sessiondb, request, self.response)
        self.userdb = userdb
        self.user = copy.deepcopy(self.userdb.db.get(self.sessionhandler.get()))
        self.request_uri = wsgiref.util.request_uri(request.environ)
        self.application_uri = wsgiref.util.application_uri(request.environ)
        if not self.application_uri.endswith("/"):
            self.application_uri += "/"

    def login(self, username):
        self.user = copy.deepcopy(self.userdb.db[username])
        self.sessionhandler.set(self.user.name)

    def logout(self):
        self.user = None
        self.sessionhandler.delete()

    def emit_content(self, content):
        self.response.data = content
        return self.response

    def emit_template(self, template, extraparams=dict()):
        self.response.content_type = "text/html; charset=utf8"
        params = dict(
            user=self.user,
            basejoin = lambda tail: urllib.basejoin(self.application_uri, tail)
        )
        params.update(extraparams)
        return self.emit_content(template.render(params).encode("utf8"))

    def emit_permredirect(self, location):
        return werkzeug.utils.redirect(
            urllib.basejoin(self.application_uri, location), 301)

    def emit_tempredirect(self, location):
        return werkzeug.utils.redirect(
            urllib.basejoin(self.application_uri, location), 307)

resp403 = Response("403 Forbidden", status="403 Forbidden")
resp404 = Response("404 File Not Found", status="404 File Not Found")
resp405 = Response("405 Method Not Allowed", status="405 Method Not Allowed")

class Application:
    def __init__(self, userdb, acapath):
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader("./templates"))
        self.sessiondb = sqlite3.connect(":memory:")
        cur = self.sessiondb.cursor()
        cur.execute(SessionHandler.create_table)
        self.sessiondb.commit()
        self.userdb = userdb
        self.acapath = acapath
        self.routingmap = werkzeug.routing.Map([
            werkzeug.routing.Rule("/", endpoint=self.render_start),
            werkzeug.routing.Rule("/login", methods=("POST",),
                                  endpoint=self.do_login),
            werkzeug.routing.Rule("/logout", methods=("POST",),
                                  endpoint=self.do_logout),
            #werkzeug.routing.Rule("/df/", endpoint=self.do_index),
            #werkzeug.routing.Rule("/df/<academy>/", endpoint=self.do_academy),
            #werkzeug.routing.Rule("/df/<academy>/<course>/", endpoint="course"),
            #werkzeug.routing.Rule("/df/<academy>/<course>/<int:page>",
            #                      endpoint=self.do_page),
            #werkzeug.routing.Rule("/df/<academy>/<course>/<int:page>/edit",
            #                      endpoint=self.do_edit),
        ])

    def getAcademy(self, name):
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            return None
        if not os.path.isdir(os.path.join(self.acapath, name)):
            return None
        return academy.Academy(os.path.join(self.acapath, name))

    def createAcademy(self, name, title, groups):
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            return False
        path = os.path.join(self.acapath, name)
        if os.path.exists(path):
            return False
        os.makedirs(path)
        aca = academy.Academy(path)
        aca.settitle(title)
        aca.setgroups(groups)
        return aca

    def listAcademies(self):
        ret = map(self.getAcademy, os.listdir(self.acapath))
        ret.sort(key=operator.attrgetter('name'))
        return ret

    @Request.application
    def __call__(self, request):
        rs = RequestState(request, self.sessiondb, self.userdb)
        try:
            endpoint, args = \
                    self.routingmap.bind_to_environ(request.environ).match()
            return endpoint(rs, **args)
        except werkzeug.routing.HTTPException, e:
            return e
        if not request.environ["PATH_INFO"]:
            return rs.emit_permredirect("")
        if request.environ["PATH_INFO"] == "/login":
            return self.do_login(rs)
        if request.environ["PATH_INFO"] == "/logout":
            return self.do_logout(rs)
        path_parts = request.environ["PATH_INFO"].split('/')
        if not path_parts[0]:
            path_parts.pop(0)
        if not path_parts or not path_parts[0]:
            if rs.user:
                return self.render_index(rs)
            else:
                return self.render_start(rs)
        if path_parts[0] == "df":
            path_parts.pop(0)
            return self.do_df(rs, path_parts)
        return resp404

    def do_login(self, rs):
        rs.response.headers.content_type = "text/plain"
        try:
            username = rs.request.form["username"]
            password = rs.request.form["password"]
            rs.request.form["submit"] # just check for existence
        except KeyError:
            return rs.emit_content("missing form fields")
        if not self.userdb.checkLogin(username, password):
            return rs.emit_content("wrong password")
        rs.login(username)
        return self.render_index(rs)

    def do_logout(self, rs):
        rs.logout()
        return self.render_start(rs)

    def do_df(self, rs, path_parts):
        path_parts = filter(None, path_parts)
        if not rs.user:
            return rs.emit_tempredirect("")
        if not path_parts:
            return self.render_index(rs)
        academy = self.getAcademy(path_parts.pop(0))
        if academy is None:
            return resp404
        if not rs.user.allowedRead(academy.name):
            return resp403
        if not path_parts:
            return self.render_academy(rs, academy)
        course = academy.getCourse(path_parts.pop(0))
        if course is None:
            return resp404
        if not rs.user.allowedRead(academy.name, course.name):
            return resp403
        if not path_parts:
            return self.render_course(rs, academy, course)
        action = path_parts.pop(0)
        if action=="createpage":
            if not rs.user.allowedWrite(academy.name, course.name):
                return resp403
            if rs.request.method != "POST":
                return resp405
            course.newpage(user=rs.user.name)
            return self.render_course(rs, academy, course)
        elif action=="moveup":
            if not rs.user.allowedWrite(academy.name, course.name):
                return resp403
            if rs.request.method != "POST":
                return resp405
            numberstr = rs.request.form["number"]
            try:
                number = int(numberstr)
            except ValueError:
                number = 0
            course.swappages(number,user=rs.user.name)
            return self.render_course(rs, academy, course)

        ## no action at course level, must be a page
        if not action.isdigit():
            return resp404
        page = int(action)
        if not path_parts:
            return self.render_show(rs, academy, course, page)
        action = path_parts.pop(0)

        if action=="edit":
            if not rs.user.allowedWrite(academy.name, course.name):
                return resp403
            version, content = course.editpage(page)
            return self.render_edit(rs, academy, course, page, version, content)
        elif action=="save":
            if not rs.user.allowedWrite(academy.name, course.name):
                return resp403
            userversion = rs.request.form["revisionstartedwith"]
            usercontent = rs.request.form["content"]
                
            ok, version, content = course.savepage(page,userversion,usercontent)
            
            issaveshow = "saveshow" in rs.request.form
            if ok and issaveshow:
                return self.render_show(rs, academy, course, page, saved=True)
            
            return self.render_edit(rs, academy, course, page, version, content, ok=ok)
            
            
        else:
            raise AssertionError("fixme: continue")

    def render_start(self, rs):
        return rs.emit_template(self.jinjaenv.get_template("start.html"))

    def render_edit(self, rs, theacademy, thecourse, thepage, theversion, thecontent, ok=None):
        params= dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            content=thecontent, ## Note: must use the provided content, as it has to fit with the version
            version=theversion,
            ok=ok)
        return rs.emit_template(self.jinjaenv.get_template("edit.html"),params)


    def render_index(self, rs):
        params = dict(
            academies=map(academy.AcademyLite, self.listAcademies()))
        return rs.emit_template(self.jinjaenv.get_template("index.html"),
                                params)

    def render_academy(self, rs, theacademy):
        return rs.emit_template(self.jinjaenv.get_template("academy.html"),
                                dict(academy=academy.AcademyLite(theacademy)))

    def render_course(self, rs, theacademy, thecourse):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse))
        return rs.emit_template(self.jinjaenv.get_template("course.html"),
                                params)

    def render_show(self, rs, theacademy, thecourse,thepage, saved=False):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            content=thecourse.showpage(thepage),
            saved=saved)
        return rs.emit_template(self.jinjaenv.get_template("show.html"),
                                params)

def main():
    userdbstore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(userdbstore)
    userdb.load()
    app = Application(userdb, './df/')
    app = TracebackMiddleware(app)
    staticfiles = dict(("/static/" + f, StaticFile("./static/" + f)) for f in
                       os.listdir("./static/"))
    app = SubdirMiddleware(app, staticfiles)
    server = SCGIServer(app, 4000)
    server.run()

if __name__ == '__main__':
    main()

