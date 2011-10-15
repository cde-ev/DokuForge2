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
import wsgiref.util
from wsgitools.applications import StaticContent, StaticFile
from wsgitools.middlewares import TracebackMiddleware, SubdirMiddleware
from wsgitools.scgi.asynchronous import SCGIServer
# import other parts of Dokuforge
import academy
import storage
import user

sysrand = random.SystemRandom()

class CookieHandler:
    def __init__(self, name="sid", bits=64):
        self.name = name
        self.bits = bits

    def get(self, environ):
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
        cookiemorsel = Cookie.Morsel()
        cookiemorsel.set(self.name, value, value)
        return ("Set-Cookie", cookiemorsel.OutputString())

    def newvalue(self):
        return "%x" % random.getrandbits(self.bits)

    def new(self):
        return self.set(self.newvalue())

    def delete(self):
        cookiemorsel = Cookie.Morsel()
        cookiemorsel.set(self.name, "", "")
        cookiemorsel["max-age"] = 0
        cookiemorsel["expires"] = "Thu, 01-Jan-1970 00:00:01 GMT"
        return ("Set-Cookie", cookiemorsel.OutputString())

class SessionHandler:
    create_table = "CREATE TABLE IF NOT EXISTS sessions " + \
                   "(sid TEXT, user TEXT, UNIQUE(sid));"

    def __init__(self, db, cookiehandler, environ=dict()):
        self.db = db
        self.cookiehandler = cookiehandler
        self.cur = db.cursor()
        self.sid = self.cookiehandler.get(environ)

    def get(self):
        if self.sid is None:
            return None
        self.cur.execute("SELECT user FROM sessions WHERE sid = ?;",
                         (self.sid.decode("utf8"),))
        results = self.cur.fetchall()
        if len(results) != 1:
            return None
        return results[0][0].encode("utf8")

    def set(self, username):
        ret = []
        if self.sid is None:
            self.sid = self.cookiehandler.newvalue()
            ret.append(self.cookiehandler.set(self.sid))
        self.cur.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?);",
                         (self.sid.decode("utf8"), username.decode("utf8")))
        self.db.commit()
        return ret

    def delete(self):
        if self.sid is None:
            return []
        self.cur.execute("DELETE FROM sessions WHERE sid = ?;",
                         (self.sid.decode("utf8"),))
        self.db.commit()
        return [self.cookiehandler.delete()]

app405 = StaticContent("405 Method Not Allowed",
                       [("Content-type", "text/plain")],
                       "405 Method Not Allowed", anymethod=True)

class RequestState:
    def __init__(self, environ, start_response, sessiondb, cookiehandler, userdb):
        self.environ = environ
        self.start_response = start_response
        self.outheaders = {}
        self.fieldstorage = None
        self.sessionhandler = SessionHandler(sessiondb, cookiehandler, environ)
        self.emitted = False
        self.userdb = userdb
        self.user = copy.deepcopy(self.userdb.db.get(self.sessionhandler.get()))
        self.request_uri = wsgiref.util.request_uri(environ)

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

    def emit(self, status):
        assert not self.emitted
        self.emitted = True
        self.start_response(status, self.outheaders.items())

    def emit_app(self, app):
        assert not self.emitted
        self.emitted = True
        return app(self.environ, self.start_response)

    def emit_content(self, content):
        self.outheaders["Content-Length"] = str(len(content))
        self.emit("200 Found")
        return [content]

    def emit_template(self, template, extraparams=dict()):
        self.outheaders["Content-Type"] = "text/html; charset=utf8"
        params = dict(user=self.user)
        params.update(extraparams)
        return self.emit_content(template.render(params).encode("utf8"))

    def emit_permredirect(self, location):
        self.outheaders["Location"] = urllib.basejoin(self.request_uri,
                                                      location)
        self.outheaders["Content-Length"] = 0
        self.emit("301 Moved Permanently")
        return []

app404 = StaticContent("404 File Not Found",
                       [("Content-type", "text/plain")],
                       "404 File Not Found", anymethod=True)

class Application:
    def __init__(self, userdb, acadbstore):
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader("./templates"))
        self.cookiehandler = CookieHandler()
        self.sessiondb = sqlite3.connect(":memory:")
        cur = self.sessiondb.cursor()
        cur.execute(SessionHandler.create_table)
        self.sessiondb.commit()
        self.userdb = userdb
        self.acadbstore = acadbstore

    def getAcademy(self, name):
        if re.match('^[-a-zA-Z0-9]*$', name) is None:
            return None
        lookup = re.findall('^' + name + ' (.*)$',
                            self.acadbstore.content(), re.MULTILINE)
        if not len(lookup) == 1:
            return None
        if not os.path.isdir(lookup[0]):
            return None
        return academy.Academy(lookup[0])

    def createAcademy(self, name, title, groups):
        if re.match('^[-a-zA-Z0-9]*$', name) is None:
            return False
        s = self.acadbstore.content()
        if not re.search('^' + name + ' ', s, re.MULTILINE) is None:
            return False
        path = './df/' + name + '/'
        if not re.search(' ' + path + '$', s, re.MULTILINE) is None:
            return False
        if os.path.exists(path):
            return False
        os.makedirs(path)
        self.acadbstore.store(self.acadbstore.content() + '\n' + name + ' '
                              + path + '\n')
        aca = academy.Academy(path)
        aca.settitle(title)
        aca.setgroups(groups)

    def listAcademies(self):
        return map(self.getAcademy,
                   re.findall('^([^ ]*) ', self.acadbstore.content(),
                              re.MULTILINE))

    def __call__(self, environ, start_response):
        rs = RequestState(environ, start_response, self.sessiondb,
                          self.cookiehandler, self.userdb)
        if not environ["PATH_INFO"]:
            return rs.emit_permredirect(rs.request_uri + "/")
        if environ["PATH_INFO"] == "/login":
            return self.do_login(rs)
        if environ["PATH_INFO"] == "/logout":
            return self.do_logout(rs)
        path_parts = environ["PATH_INFO"].split('/')
        if not path_parts[0]:
            path_parts.pop(0)
        if not path_parts or not path_parts[0]:
            return self.render_start(rs)
        if path_parts[0] == "df":
            path_parts.pop(0)
            return self.do_df(rs, path_parts)
        return rs.emit_app(app404)

    def do_login(self, rs):
        if rs.environ["REQUEST_METHOD"] != "POST":
            return rs.emit_app(app405)
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
            return rs.emit_app(app405)
        rs.logout()
        return self.render_start(rs)

    def do_df(self, rs, path_parts):
        if not path_parts:
            return self.render_index(rs)
        # TODO: path_parts[0] is academy name
        raise AssertionError("fixme: continue")

    def render_start(self, rs):
        return rs.emit_template(self.jinjaenv.get_template("start.html"))

    def render_edit(self, rs):
        return rs.emit_template(self.jinjaenv.get_template("edit.html"),
                                dict(content="edit me"))

    def render_index(self, rs):
        params = dict(
            academies=map(academy.AcademyLite, self.listAcademies()))
        return rs.emit_template(self.jinjaenv.get_template("index.html"),
                                params)

    def render_academy(self, rs):
        return rs.emit_template(self.jinjaenv.get_template("academy.html"),
                                dict(courses=[]))

def main():
    userdbstore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(userdbstore)
    userdb.load()
    acadbstore = storage.Storage('work', 'acadb')
    app = Application(userdb, acadbstore)
    app = TracebackMiddleware(app)
    staticfiles = dict(("/static/" + f, StaticFile("./static/" + f)) for f in
                       os.listdir("./static/"))
    app = SubdirMiddleware(app, staticfiles)
    server = SCGIServer(app, 4000)
    server.run()

if __name__ == '__main__':
    main()

