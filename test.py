#!/usr/bin/env python
# -*- coding: utf-8 -*-

# pylint: disable=E1102
# Pylint thinks that no methods on DokuforgeTests.br (a WSGIBrowser instance)
# are callable. This is clearly wrong and renders this message useless for this
# file.

from cStringIO import StringIO
from httplib import HTTPMessage
import mechanize
import re
import shutil
import sys
import tempfile
import unittest
from urllib import addinfourl
from urllib2 import BaseHandler
from wsgiref.validate import validator
import subprocess

import createexample
from dokuforge import buildapp
from dokuforge.paths import PathConfig

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
    (u"some ' " + u'" quotes', u"some &#39; &#34; quotes")
    ]

class DokuforgeTests(unittest.TestCase):
    url = "http://www.dokuforge.de"
    def setUp(self):
        global theapplication
        self.tmpdir = tempfile.mkdtemp(prefix="dokuforge")
        self.pathconfig = PathConfig()
        self.pathconfig.rootdir = self.tmpdir
        createexample.main(size=1, pc=self.pathconfig)
        app = buildapp(self.pathconfig)
        theapplication = validator(app)
        self.br = WSGIBrowser()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, True)

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
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.is_loggedin()
        self.assertTrue("Roh-Export" in self.get_data())

    def testPage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.is_loggedin()
        self.assertTrue("neues Bild hinzuf" in self.get_data())

    def testEdit(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        for (inputstr, outputstr) in teststrings:
            self.br.open(self.br.click_link(text="Editieren"))
            form = list(self.br.forms())[1]
            form["content"] = inputstr.encode("utf8")
            self.br.open(form.click(label="Speichern und Beenden"))
            self.assertTrue(outputstr.encode("utf8") in self.get_data())
        self.is_loggedin()

    def testMarkup(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(text="Editieren"))
        form = list(self.br.forms())[1]
        form["content"] = \
"""[Section]
(Authors)
*keyword*, $\\sqrt{2}$ and _emphasis_
$$\\sqrt{2}$$
[[subsection]]
- bullet1
- bullet2
chars like < > & " to be escaped and an { ednote \\end{ednote} }
"""
        self.br.open(form.click(label="Speichern und Beenden"))
        content = self.get_data()
        self.assertTrue("$\\sqrt{2}$" in content)
        self.assertTrue("ednote \\end{ednote}" in content)
        self.is_loggedin()

    def testMovePage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Hochrücken".encode("utf8")))
        self.is_loggedin()

    def testCreatePage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        form = list(self.br.forms())[2]
        self.br.open(form.click(label=u"Neuen Teil anlegen".encode("utf8")))
        self.is_loggedin()
        self.assertTrue("Teil&nbsp;#2" in self.get_data())

    def testCourseTitle(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
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
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.assertFalse("Teil&nbsp;#0" in self.get_data())
        self.is_loggedin()

    def testRestorePage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/!deadpages$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label="wiederherstellen"))
        self.assertTrue("Teil&nbsp;#0" in self.get_data())
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

    def testExport(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(text="Editieren"))
        form = list(self.br.forms())[1]
        form["content"] = \
"""[Section]
(Authors)
*keyword*, $\\sqrt{2}$ and _emphasis_
$$\\sqrt{2}$$
[[subsection]]
- bullet1
- bullet2
chars like < > & " % to be escaped and an { ednote \\end{ednote} }
"""
        self.br.open(form.click(label="Speichern und Beenden"))
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("/!export$")))
        p = subprocess.Popen(['file', '-'], stdin = subprocess.PIPE,
                             stdout=subprocess.PIPE)
        self.assertTrue("bzip2 compressed data" in
                        p.communicate(self.get_data())[0])

    def testAcademyGroups(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(text="Gruppen bearbeiten"))
        form = list(self.br.forms())[1]
        form["groups"] = ["cde"]
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Gruppen erfolgreich bearbeitet." in self.get_data())
        form = list(self.br.forms())[1]
        # hack an invalid group
        mechanize.Item(form.find_control("groups"), dict(value="spam"))
        form["groups"] = ["cde", "spam"]
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
        self.assertTrue("Interner Name nicht wohlgeformt!" in self.get_data())
        self.is_loggedin()

    def testCreateAcademy(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(url_regex=re.compile("/createacademy$")))
        form = list(self.br.forms())[1]
        form["name"] = "newacademy-2001"
        form["title"] = "Testakademie"
        form["groups"] = ["cde"]
        self.br.open(form.click(label="Akademie anlegen"))
        self.assertTrue("Testakademie" in self.get_data())
        self.assertTrue("X-Akademie" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/createacademy$")))
        form = list(self.br.forms())[1]
        form["name"] = "foo_bar"
        form["title"] = "next Testakademie"
        form["groups"] = ["cde"]
        self.br.open(form.click(label="Akademie anlegen"))
        self.assertTrue("Interner Name nicht wohlgeformt!" in self.get_data())
        form = list(self.br.forms())[1]
        form["name"] = "foobar"
        form["title"] = "next Testakademie"
        # hack an invalid group
        mechanize.Item(form.find_control("groups"), dict(value="spam"))
        form["groups"] = ["cde", "spam"]
        self.br.open(form.click(label="Akademie anlegen"))
        self.assertTrue("Nichtexistente Gruppe gefunden!" in self.get_data())
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
        self.assertTrue("Es ist ein allgemeiner Parser-Fehler aufgetreten!" in self.get_data())
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
        self.assertTrue("Es ist ein allgemeiner Parser-Fehler aufgetreten!" in self.get_data())
        self.is_loggedin()

    def testStyleguide(self):
        self.br.open(self.url)
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.assertTrue("Richtlinien für die Erstellung der Dokumentation" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/intro$")))
        self.assertTrue(u"Über die Geschichte, den Sinn und die Philosophie von DokuForge".encode("utf8") in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/hilfe$")))
        self.assertTrue("Ein kurzer Leitfaden für die Benutzung von DokuForge" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/grundlagen$")))
        self.assertTrue("Grundlagen von DokuForge" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/abbildungen$")))
        self.assertTrue(u"Wie werden Abbildungen in DokuForge eingefügt?".encode("utf8") in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/mathe$")))
        self.assertTrue("Wie werden Formeln gesetzt?" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/spezielles$")))
        self.assertTrue(u"Sondersonderwünsche".encode("utf8") in self.get_data())
        self.br.open(self.br.click_link(text="Login"))
        self.do_login()
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.assertTrue("Richtlinien für die Erstellung der Dokumentation" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/intro$")))
        self.assertTrue(u"Über die Geschichte, den Sinn und die Philosophie von DokuForge".encode("utf8") in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/hilfe$")))
        self.assertTrue("Ein kurzer Leitfaden für die Benutzung von DokuForge" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/grundlagen$")))
        self.assertTrue("Grundlagen von DokuForge" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/abbildungen$")))
        self.assertTrue(u"Wie werden Abbildungen in DokuForge eingefügt?".encode("utf8") in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/mathe$")))
        self.assertTrue("Wie werden Formeln gesetzt?" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/style/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/style/spezielles$")))
        self.assertTrue(u"Sondersonderwünsche".encode("utf8") in self.get_data())
        self.is_loggedin()

    def testAddBlob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/!addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.assertTrue("Abbildungen" in self.get_data())
        self.assertTrue("#[0] (README-rlog.txt)" in self.get_data())
        self.is_loggedin()

    def testShowBlob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/!addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/0/$")))
        self.assertTrue("Bildunterschrift/Kommentar: Shiny blob" in self.get_data())
        self.assertTrue("K&uuml;rzel: blob" in self.get_data())
        self.is_loggedin()

    def testMD5Blob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/!addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/0/!md5$")))
        self.assertTrue("MD5 Summe des Bildes ist" in self.get_data())
        self.is_loggedin()

    def testEditBlob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/!addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/0/!edit$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Real Shiny blob"
        form["label"] = "blub"
        form["name"] = "README"
        self.br.open(form.click(label="Speichern"))
        self.assertTrue("Bildunterschrift/Kommentar: Real Shiny blob" in self.get_data())
        self.assertTrue("K&uuml;rzel: blub" in self.get_data())
        self.assertTrue("Dateiname: README" in self.get_data())
        self.is_loggedin()

    def testDeleteBlob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/!addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.assertTrue("Abbildungen" in self.get_data())
        self.assertTrue("#[0] (README-rlog.txt)" in self.get_data())
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.assertTrue("Keine Bilder zu diesem Teil gefunden." in self.get_data())
        self.assertFalse("#[0] (README-rlog.txt)" in self.get_data())
        self.is_loggedin()

    def testRestoreBlob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/!addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.assertTrue("Keine Bilder zu diesem Teil gefunden." in self.get_data())
        self.assertFalse("#[0] (README-rlog.txt)" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/!deadblobs$")))
        self.assertTrue("#[0] (README-rlog.txt)" in self.get_data())
        form = list(self.br.forms())[1]
        self.br.open(form.click(label="wiederherstellen"))
        self.assertTrue("Abbildungen" in self.get_data())
        self.assertTrue("#[0] (README-rlog.txt)" in self.get_data())
        self.is_loggedin()

    def testAddBlobEmptyLabel(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("kurs01/0/!addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = ""
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        self.assertTrue(u"Kürzel nicht wohlgeformt!".encode("utf8") in self.get_data())
        self.is_loggedin()

if __name__ == '__main__':
    unittest.main()
