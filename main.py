#!/usr/bin/env python

from cgi import FieldStorage
import Cookie
import jinja2
import random
import os
import sqlite3
from wsgitools.applications import StaticContent, StaticFile
from wsgitools.middlewares import TracebackMiddleware, SubdirMiddleware
from wsgitools.scgi.asynchronous import SCGIServer

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
    def __init__(self, environ, start_response, sessiondb, cookiehandler):
        self.environ = environ
        self.start_response = start_response
        self.outheaders = {}
        self.fieldstorage = None
        self.sessionhandler = SessionHandler(sessiondb, cookiehandler, environ)
        self.username = self.sessionhandler.get()

    def parse_request(self):
        self.fieldstorage = FieldStorage(environ=self.environ,
                                         fp=self.environ["wsgi.input"])
        return self.fieldstorage

    def login(self, username):
        self.username = username
        self.outheaders.update(dict(self.sessionhandler.set(username)))

    def logout(self):
        self.username = None
        self.outheaders.update(dict(self.sessionhandler.delete()))

    def get_field(self, key):
        return self.fieldstorage[key].value # raises KeyError

    def emit(self, status):
        self.start_response(status, self.outheaders.items())

class Application:
    def __init__(self):
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader("./templates"))
        self.cookiehandler = CookieHandler()
        self.sessiondb = sqlite3.connect(":memory:")
        cur = self.sessiondb.cursor()
        cur.execute(SessionHandler.create_table)
        self.sessiondb.commit()

    def __call__(self, environ, start_response):
        rs = RequestState(environ, start_response, self.sessiondb,
                          self.cookiehandler)
        if environ["PATH_INFO"] == "/login":
            return self.do_login(rs)
        rs.outheaders["Content-Type"] = "text/html; charset=utf8"
        # toggle the login for example
        if rs.username is None:
            rs.login("foo")
        else:
            rs.logout()
        content = self.jinjaenv.get_template("start.html").render({}) \
                  .encode("utf8")
        rs.emit("200 OK")
        return [content]

    def do_login(self, rs):
        if rs.environ["REQUEST_METHOD"] != "POST":
            return app405(rs.environ, rs.start_response)
        rs.parse_request()
        rs.outheaders["Content-Type"] = "text/plain"
        try:
            username = rs.get_field("username")
            password = rs.get_field("password")
            rs.get_field("submit") # just check for existence
        except KeyError:
            rs.emit("200 OK")
            return ["missing form fields"]
        if username != password: # FIXME: silly pw check
            rs.emit("200 OK")
            return ["wrong password"]
        rs.login(username)
        rs.emit("200 OK")
        return ["logged in"]

def main():
    app = Application()
    app = TracebackMiddleware(app)
    staticfiles = dict(("/static/" + f, StaticFile("./static/" + f)) for f in
                       os.listdir("./static/"))
    app = SubdirMiddleware(app, staticfiles)
    server = SCGIServer(app, 4000)
    server.run()

if __name__ == '__main__':
    main()
