#!/usr/bin/env python

import Cookie
import jinja2
import random
import os
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
            return cookie[self.name].value
        except KeyError:
            return None

    def set(self, value):
        cookiemorsel = Cookie.Morsel()
        cookiemorsel.set(self.name, value, value)
        return ("Set-Cookie", cookiemorsel.OutputString())

    def newvalue(self):
        return "%x" % random.getrandbits(self.bits)

    def new(self):
        return self.set(self.newvalue())

class Application:
    def __init__(self):
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader("./templates"))
        self.cookiehandler = CookieHandler()
    def __call__(self, environ, start_response):
        headers = {
            "Content-Type": "text/html; charset=utf8"
        }
        content = self.jinjaenv.get_template("base.html").render({}) \
                  .encode("utf8")
        cookie = self.cookiehandler.get(environ)
        if cookie is None:
            headers.__setitem__(*self.cookiehandler.new())
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
