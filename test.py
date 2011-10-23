#!/usr/bin/env python

from cStringIO import StringIO
from httplib import HTTPMessage
import mechanize
import re
import shutil
import sys
import unittest
from urllib import addinfourl
from urllib2 import BaseHandler
from wsgiref.validate import validator

import createexample
from main import Application
from storage import Storage
from user import UserDB

theapplication = None

class WSGIHandler(BaseHandler):
    environ_base = {
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "wsgi.version": (1, 0),
        "wsgi.errors": sys.stderr,
        "wsgi.url_scheme": "http",
        "SERVER_PROTOCOL": "HTTP/1.1",
    }
    def http_request(self, request):
        return request

    def http_open(self, request):
        environ = self.environ_base.copy()
        environ["REQUEST_METHOD"] = request.get_method()
        environ["SERVER_NAME"] = request.get_host()
        environ["SERVER_PORT"] = "%d" % (request.port or 80)
        environ["SCRIPT_NAME"] = ""
        environ["PATH_INFO"] = request.get_selector()
        environ["QUERY_STRING"] = "" # FIXME
        if request.has_data():
            reqdata = request.get_data()
            environ["wsgi.input"] = StringIO(reqdata)
            environ["CONTENT_LENGTH"] = str(len(reqdata))
            environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
        else:
            environ["wsgi.input"] = StringIO()
            environ["CONTENT_LENGTH"] = "0"
        environ.update(("HTTP_%s" % key.replace("-", "_").upper(), value)
                       for key, value in request.headers.items())
        environ.update(("HTTP_%s" % key.replace("-", "_").upper(), value)
                       for key, value in request.unredirected_hdrs.items())
        if "HTTP_CONTENT_TYPE" in environ:
            environ["CONTENT_TYPE"] = environ.pop("HTTP_CONTENT_TYPE")
        fp = StringIO()
        wsgiresp = []
        def start_response(status, headers):
            wsgiresp.append(status)
            for item in headers:
                fp.write("%s: %s\r\n" % item)
            fp.write("\r\n")
            return fp.write
        iterator = theapplication(environ, start_response)
        for data in iterator:
            fp.write(data)
        if hasattr(iterator, "close"):
            iterator.close()
        fp.seek(0)
        httpmessage = HTTPMessage(fp)
        resp = addinfourl(fp, httpmessage, request.get_full_url())
        code, msg = wsgiresp[0].split(' ', 1)
        resp.code = int(code)
        resp.msg = msg
        return resp

class WSGIBrowser(mechanize.Browser):
    handler_classes = mechanize.Browser.handler_classes.copy()
    handler_classes["http"] = WSGIHandler

class DokuforgeTests(unittest.TestCase):
    url = "http://www.dokuforge.de"
    def setUp(self):
        global theapplication
        shutil.rmtree("df", True)
        shutil.rmtree("work", True)
        createexample.main()
        userdbstore = Storage('work', 'userdb')
        userdb = UserDB(userdbstore)
        userdb.load()
        groupstore = Storage('work', 'groupdb')
        app = Application(userdb, groupstore, './df/', "./templates/", "./style/")
        theapplication = validator(app)
        self.br = WSGIBrowser()

    def get_data(self):
        return self.br.response().get_data()

    def do_login(self, username="bob", password="secret"):
        forms = list(self.br.forms())
        self.assertEqual(1, len(forms))
        form = forms[0]
        form["username"] = username
        form["password"] = password
        self.br.open(form.click())

    def do_logout(self):
        forms = list(self.br.forms())
        form = forms[0]
        self.br.open(form.click())

    def is_loggedin(self):
        self.assertTrue("!logout" in self.get_data())

    def testLogin(self):
        self.br.open(self.url)
        self.do_login()
        self.is_loggedin()

    def testLoginFailed(self):
        self.br.open(self.url)
        self.do_login(username="nonexistent")
        # FIXME: sane error message
        self.assertEqual(self.get_data(), "wrong password")

    def testLoginClick(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="Dokuforge"))
        self.is_loggedin()

    def testLogout(self):
        self.br.open(self.url)
        self.do_login()
        self.do_logout()
        self.assertFalse("!logout" in self.get_data())

    def testAcademy(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.is_loggedin()
        self.assertTrue("Exportieren" in self.get_data())

    def testEdit(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(text="Editieren"))
        form = list(self.br.forms())[1]
        form["content"] = "wonderful content"
        self.br.open(form.click(label="Speichern und Beenden"))
        self.assertTrue("wonderful content" in self.get_data())

if __name__ == '__main__':
    unittest.main()
