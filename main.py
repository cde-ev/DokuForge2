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
        fs = FieldStorage(environ=environ, fp=environ["wsgi.input"])
        headers = {
            "Content-Type": "text/html; charset=utf8"
        }
        content = self.jinjaenv.get_template("base.html").render({}) \
                  .encode("utf8")
        sh = SessionHandler(self.sessiondb, self.cookiehandler, environ)
        user = sh.get()
        # toggle the login for example
        if user is None:
            headers.update(dict(sh.set("foo"))) # set cookie
        else:
            headers.update(dict(sh.delete()))
        return StaticContent("200 OK",
                             list(headers.items()),
                             content)(environ, start_response)

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
