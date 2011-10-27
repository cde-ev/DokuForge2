#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

teststrings = [
    (u"simple string", u"simple string"),
    (u"some chars <>/& here", u"some chars &lt;&gt;/&amp; here"),
    (u"exotic äöüß 囲碁 chars", u"exotic äöüß 囲碁 chars"),
    (u"some ' " + u' " quotes', u"some &#39;  &#34; quotes")
    ]

class DokuforgeTests(unittest.TestCase):
    url = "http://www.dokuforge.de"
    def setUp(self):
        global theapplication
        shutil.rmtree("df", True)
        shutil.rmtree("work", True)
        createexample.main(size = 1)
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
        self.assertTrue("/logout" in self.get_data())

    def testLogin(self):
        self.br.open(self.url)
        self.do_login()
        self.is_loggedin()

    def testLoginFailedUsername(self):
        self.br.open(self.url)
        self.do_login(username="nonexistent")
        # FIXME: sane error message
        self.assertEqual(self.get_data(), "wrong password")

    def testLoginFailedPassword(self):
        self.br.open(self.url)
        self.do_login(password="wrong")
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
        self.assertFalse("/logout" in self.get_data())

    def testAcademy(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.is_loggedin()
        self.assertTrue("Exportieren" in self.get_data())

    def testCourse(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.is_loggedin()
        self.assertTrue("Roh-Export" in self.get_data())

    def testPage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.is_loggedin()
        self.assertTrue("neues Bild hinzuf" in self.get_data())

    def testEdit(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        for (inputstr, outputstr) in teststrings:
            self.br.open(self.br.click_link(text="Editieren"))
            form = list(self.br.forms())[1]
            form["content"] = inputstr.encode("utf8")
            self.br.open(form.click(label="Speichern und Beenden"))
            self.assertTrue(outputstr.encode("utf8") in self.get_data())
        self.is_loggedin()

    def testMovePage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Hochrücken".encode("utf8")))
        self.is_loggedin()

    def testCreatePage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        form = list(self.br.forms())[2]
        self.br.open(form.click(label=u"Neuen Teil anlegen".encode("utf8")))
        self.is_loggedin()
        self.assertTrue("Teil #2" in self.get_data())

    def testCourseTitle(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/!title$")))
        for (inputstr, outputstr) in teststrings:
            form = list(self.br.forms())[1]
            form["content"] = inputstr.encode("utf8")
            self.br.open(form.click(label="Speichern und Editieren"))
            self.assertTrue(outputstr.encode("utf8") in self.get_data())
        self.is_loggedin()

    def testDeletePage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.assertFalse("Teil #0" in self.get_data())
        self.is_loggedin()

    def testRestorePage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/!deadpages$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label="wiederherstellen"))
        self.assertTrue("Teil #0" in self.get_data())
        self.is_loggedin()

    def testAcademyTitle(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("/!title$")))
        for (inputstr, outputstr) in teststrings:
            form = list(self.br.forms())[1]
            form["content"] = inputstr.encode("utf8")
            self.br.open(form.click(label="Speichern und Editieren"))
            self.assertTrue(outputstr.encode("utf8") in self.get_data())
        self.is_loggedin()

    def testAcademyGroups(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(text="Gruppen bearbeiten"))
        form = list(self.br.forms())[1]
        form["content"] = "cde qed"
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Aenderungen erfolgreich gespeichert." in self.get_data())
        form = list(self.br.forms())[1]
        form["content"] = "cde spam"
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Nichtexistente Gruppe gefunden!" in self.get_data())
        self.is_loggedin()

    def testCreateCourse(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("/!createcourse$")))
        form = list(self.br.forms())[1]
        form["name"] = "course03"
        form["title"] = "Testkurs"
        self.br.open(form.click(label=u"Kurs hinzufügen".encode("utf8")))
        self.assertTrue("Area51" in self.get_data())
        self.assertTrue("Testkurs" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/!createcourse$")))
        form = list(self.br.forms())[1]
        form["name"] = "foo_bar"
        form["title"] = "next Testkurs"
        self.br.open(form.click(label=u"Kurs hinzufügen".encode("utf8")))
        self.assertTrue("Die Kurserstellung war nicht erfolgreich." in self.get_data())
        self.is_loggedin()

    def testCreateAcademy(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(url_regex=re.compile("/createacademy$")))
        form = list(self.br.forms())[1]
        form["name"] = "newacademy-2001"
        form["title"] = "Testakademie"
        form["groups"] = "cde"
        self.br.open(form.click(label="Akademie anlegen"))
        self.assertTrue("Testakademie" in self.get_data())
        self.assertTrue("X-Akademie" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/createacademy$")))
        form = list(self.br.forms())[1]
        form["name"] = "foo_bar"
        form["title"] = "next Testakademie"
        form["groups"] = "cde"
        self.br.open(form.click(label="Akademie anlegen"))
        self.assertTrue("Die Akademieerstellung war nicht erfolgreich." in self.get_data())
        form = list(self.br.forms())[1]
        form["name"] = "foobar"
        form["title"] = "next Testakademie"
        form["groups"] = "cde spam"
        self.br.open(form.click(label="Akademie anlegen"))
        self.assertTrue("Die Akademieerstellung war nicht erfolgreich." in self.get_data())
        self.is_loggedin()

    def testGroups(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(url_regex=re.compile("/groups/$")))
        form = list(self.br.forms())[1]
        form["content"] = """[cde]
title = CdE-Akademien

[spam]
title = Wie der Name sagt
"""
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Aenderungen erfolgreich gespeichert." in self.get_data())
        form = list(self.br.forms())[1]
        form["content"] = """[cde]
title = CdE-Akademien

[spam
title = Wie der Name sagt
"""
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Es ist ein Parser Error aufgetreten!" in self.get_data())
        self.is_loggedin()

    def testAdmin(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(url_regex=re.compile("/admin/$")))
        form = list(self.br.forms())[1]
        form["content"] = """[bob]
name = bob
status = ueberadmin
password = secret
permissions = df_superadmin True,df_admin True
"""
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Aenderungen erfolgreich gespeichert." in self.get_data())
        form = list(self.br.forms())[1]
        form["content"] = """[bob
name = bob
status = ueberadmin
password = secret
permissions = df_superadmin True,df_admin True
"""
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Es ist ein Parser Error aufgetreten!" in self.get_data())
        self.is_loggedin()

if __name__ == '__main__':
    unittest.main()
