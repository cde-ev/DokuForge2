#!/usr/bin/env python

from wsgitools.scgi.asynchronous import SCGIServer

def app(environ, start_response):
    start_response("200 OK", [])
    return []

def main():
    server = SCGIServer(app, 4000)
    server.run()

if __name__ == '__main__':
    main()
