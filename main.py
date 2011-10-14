#!/usr/bin/env python

import jinja2
from wsgitools.applications import StaticContent
from wsgitools.middlewares import TracebackMiddleware
from wsgitools.scgi.asynchronous import SCGIServer

class Application:
    def __init__(self):
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader("./templates"))
    def __call__(self, environ, start_response):
        content = self.jinjaenv.get_template("base.html").render({}) \
                  .encode("utf8")
        return StaticContent("200 OK",
                             [("Content-Type", "text/html; charset=utf8")],
                             content)(environ, start_response)

def main():
    app = Application()
    app = TracebackMiddleware(app)
    server = SCGIServer(app, 4000)
    server.run()

if __name__ == '__main__':
    main()
