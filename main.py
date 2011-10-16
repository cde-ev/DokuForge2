#!/usr/bin/env python

from cgi import FieldStorage
import Cookie
import jinja2
import random
import os
import sqlite3
import copy
import re
import urllib
import werkzeug.utils
from werkzeug.wrappers import Request, Response
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

class CookieHandler:
    """Parse and manipulate cookies."""
    def __init__(self, name="sid", bits=64):
        """
        @type name: str
        @param name: the name of the cookie
        @type bits: int
        @param bits: number of bits to use for the session id
        """
        assert name.isalnum()
        assert bits > 0
        self.name = name
        self.bits = bits

    def get(self, environ):
        """
        @type environ: dict
        @rtype: str or None
        @returns: the session id if a cookie was found and None otherwise
        """
        cookiestr = environ.get("HTTP_COOKIE")
        if not cookiestr:
            return None
        cookie = Cookie.SimpleCookie()
        try:
            cookie.load(cookiestr)
        except Cookie.CookieError:
            return None
        try:
            value = cookie[self.name].value
        except KeyError:
            return None
        else:
            if value.isalnum():
                return value
            return None

    def set(self, value):
        """
        @type value: str
        @param value: session id
        @rtype: (str, str)
        @returns: a header as (headername, headervalue) setting the cookie
        """
        cookiemorsel = Cookie.Morsel()
        cookiemorsel.set(self.name, value, value)
        return ("Set-Cookie", cookiemorsel.OutputString())

    def newvalue(self):
        """
        @rtype: str
        @returns: a string with the randomness passed to the ctor
        """
        return "%x" % random.getrandbits(self.bits)

    def new(self):
        """
        @rtype: (str, str)
        @returns: a header as (headername, headervalue) setting a new cookie
        """
        return self.set(self.newvalue())

    def delete(self):
        """
        @rtype: (str, str)
        @returns: a header as (headername, headervalue) deleting the cookie
        """
        cookiemorsel = Cookie.Morsel()
        cookiemorsel.set(self.name, "", "")
        cookiemorsel["max-age"] = 0
        cookiemorsel["expires"] = "Thu, 01-Jan-1970 00:00:01 GMT"
        return ("Set-Cookie", cookiemorsel.OutputString())

class SessionHandler:
    """Associate users with session ids in a DBAPI2 database."""
    create_table = "CREATE TABLE IF NOT EXISTS sessions " + \
                   "(sid TEXT, user TEXT, UNIQUE(sid));"

    def __init__(self, db, cookiehandler, environ=dict()):
        """
        @param db: a DBAPI2 database that has a sessions table as described
                in the create_table class variable
        @type cookiehandler: CookieHandler
        @type environ: dict
        """
        self.db = db
        self.cookiehandler = cookiehandler
        self.cur = db.cursor()
        self.sid = self.cookiehandler.get(environ)

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
        @rtype: [(str, str)]
        @returns: a list of headers to be sent with the http response
        """
        ret = []
        if self.sid is None:
            self.sid = self.cookiehandler.newvalue()
            ret.append(self.cookiehandler.set(self.sid))
        self.cur.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?);",
                         (self.sid.decode("utf8"), username.decode("utf8")))
        self.db.commit()
        return ret

    def delete(self):
        """Delete a user session.
        @rtype: [(str, str)]
        @returns: a list of headers to be sent with the http response
        """
        if self.sid is None:
            return []
        self.cur.execute("DELETE FROM sessions WHERE sid = ?;",
                         (self.sid.decode("utf8"),))
        self.db.commit()
        return [self.cookiehandler.delete()]

class RequestState:
    def __init__(self, environ, sessiondb, cookiehandler, userdb):
        self.environ = environ
        self.outheaders = {}
        self.fieldstorage = None
        self.sessionhandler = SessionHandler(sessiondb, cookiehandler, environ)
        self.userdb = userdb
        self.user = copy.deepcopy(self.userdb.db.get(self.sessionhandler.get()))
        self.request_uri = wsgiref.util.request_uri(environ)
        self.application_uri = wsgiref.util.application_uri(environ)
        if not self.application_uri.endswith("/"):
            self.application_uri += "/"

    def parse_request(self):
        self.fieldstorage = FieldStorage(environ=self.environ,
                                         fp=self.environ["wsgi.input"])
        return self.fieldstorage

    def login(self, username):
        self.user = copy.deepcopy(self.userdb.db[username])
        self.outheaders.update(dict(self.sessionhandler.set(self.user.name)))

    def logout(self):
        self.user = None
        self.outheaders.update(dict(self.sessionhandler.delete()))

    def get_field(self, key):
        return self.fieldstorage[key].value # raises KeyError

    def emit_content(self, content):
        return Response(content, headers=self.outheaders)

    def emit_template(self, template, extraparams=dict()):
        self.outheaders["Content-Type"] = "text/html; charset=utf8"
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
        self.cookiehandler = CookieHandler()
        self.sessiondb = sqlite3.connect(":memory:")
        cur = self.sessiondb.cursor()
        cur.execute(SessionHandler.create_table)
        self.sessiondb.commit()
        self.userdb = userdb
        self.acapath = acapath

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
        rs = RequestState(request.environ, self.sessiondb, self.cookiehandler,
                          self.userdb)
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
        if rs.environ["REQUEST_METHOD"] != "POST":
            return resp405
        rs.parse_request()
        rs.outheaders["Content-Type"] = "text/plain"
        try:
            username = rs.get_field("username")
            password = rs.get_field("password")
            rs.get_field("submit") # just check for existence
        except KeyError:
            return rs.emit_content("missing form fields")
        if not self.userdb.checkLogin(username, password):
            return rs.emit_content("wrong password")
        rs.login(username)
        return self.render_index(rs)

    def do_logout(self, rs):
        if rs.environ["REQUEST_METHOD"] != "POST":
            return resp405
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
            if rs.environ["REQUEST_METHOD"] != "POST":
                return resp405
            course.newpage(user=rs.user.name)
            return self.render_course(rs, academy, course)
        elif action=="moveup":
            if not rs.user.allowedWrite(academy.name, course.name):
                return resp403
            if rs.environ["REQUEST_METHOD"] != "POST":
                return resp405
            rs.parse_request()
            numberstr = rs.get_field("number")
            try:
                number = int(numberstr)
            except KeyError:
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
            rs.parse_request()
            userversion = rs.get_field("revisionstartedwith")
            usercontent = rs.get_field("content")

            ok, version, content = course.savepage(page,userversion,usercontent)
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

    def render_show(self, rs, theacademy, thecourse,thepage):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            content=thecourse.showpage(thepage))
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

