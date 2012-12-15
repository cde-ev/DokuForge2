#!/usr/bin/env python
# -*- coding: utf-8 -*-

# pylint: disable=E1102
# Pylint thinks that no methods on DokuforgeTests.br (a WSGIBrowser instance)
# are callable. This is clearly wrong and renders this message useless for this
# file.

import gzip
from httplib import HTTPMessage
import io
import mechanize
import os
import re
import shutil
import sys
import random
import tempfile
import unittest
from urllib import addinfourl, unquote
from urllib2 import BaseHandler
from wsgiref.validate import validator

import createexample
from dokuforge import buildapp
from dokuforge.paths import PathConfig
from dokuforge.parser import dfLineGroupParser
from dokuforge.common import TarWriter, Sortkeys
from dokuforge.course import Course
from dokuforge.academy import Academy

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

    def __init__(self, application):
        self.application = application

    @classmethod
    def creator(cls, application):
        def create():
            return cls(application)
        return create

    def http_request(self, request):
        return request

    def http_open(self, request):
        environ = self.environ_base.copy()
        environ["REQUEST_METHOD"] = request.get_method()
        environ["SERVER_NAME"] = request.get_host()
        environ["SERVER_PORT"] = "%d" % (request.port or 80)
        environ["SCRIPT_NAME"] = ""
        environ["PATH_INFO"] = unquote(request.get_selector())
        environ["QUERY_STRING"] = "" # FIXME
        if request.has_data():
            reqdata = request.get_data()
            environ["wsgi.input"] = io.BytesIO(reqdata)
            environ["CONTENT_LENGTH"] = str(len(reqdata))
            environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
        else:
            environ["wsgi.input"] = io.BytesIO()
            environ["CONTENT_LENGTH"] = "0"
        environ.update(("HTTP_%s" % key.replace("-", "_").upper(), value)
                       for key, value in request.headers.items())
        environ.update(("HTTP_%s" % key.replace("-", "_").upper(), value)
                       for key, value in request.unredirected_hdrs.items())
        if "HTTP_CONTENT_TYPE" in environ:
            environ["CONTENT_TYPE"] = environ.pop("HTTP_CONTENT_TYPE")
        fp = io.BytesIO()
        wsgiresp = []
        def start_response(status, headers):
            wsgiresp.append(status)
            for item in headers:
                fp.write("%s: %s\r\n" % item)
            fp.write("\r\n")
            return fp.write
        iterator = self.application(environ, start_response)
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

try:
    mechanize_Item = mechanize.Item
except AttributeError:
    from ClientForm import Item as mechanize_Item

class WSGIBrowser(mechanize.Browser):
    def __init__(self, application):
        self.handler_classes = mechanize.Browser.handler_classes.copy()
        self.handler_classes["http"] = WSGIHandler.creator(application)
        mechanize.Browser.__init__(self)

teststrings = [
    (u"simple string", u"simple string"),
    (u"some chars <>/& here", u"some chars &lt;&gt;/&amp; here"),
    (u"exotic äöüß 囲碁 chars", u"exotic äöüß 囲碁 chars"),
    (u"some ' " + u'" quotes', u"some &#39; &#34; quotes")
    ]


class DfTestCase(unittest.TestCase):
    """
    Class were all units tests for dokuforge derive from. The
    class itself only provides utility functions and does not
    contain any tests.
    """
    def assertIsTar(self, octets):
        blocksize = 512
        # there must be at least the 2 terminating 0-blocks
        self.assertTrue(len(octets) >= 2 * blocksize)
        # a tar archive is a sequence of complete blocks
        self.assertTrue(len(octets) % blocksize == 0)
        # there is at least the terminating 0-block
        self.assertTrue("\0\0\0\0\0\0\0\0\0\0" in octets)

    def assertIsTarGz(self, octets):
        f = gzip.GzipFile('dummyfilename', 'rb', 9, io.BytesIO(octets))
        self.assertIsTar(f.read())

class TarWriterTests(DfTestCase):
    def testUncompressed(self):
        tarwriter = TarWriter()
        tar = b''
        tar = tar + tarwriter.addChunk('myFile', 'contents')
        tar = tar + tarwriter.close()
        self.assertIsTar(tar)
        
    def testGzip(self):
        tarwriter = TarWriter(gzip=True)
        tar = b''
        tar = tar + tarwriter.addChunk('myFile', 'contents')
        tar = tar + tarwriter.close()
        self.assertIsTarGz(tar)

class DokuforgeWebTests(DfTestCase):
    url = "http://www.dokuforge.de"
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="dokuforge")
        self.pathconfig = PathConfig()
        self.pathconfig.rootdir = self.tmpdir
        createexample.main(size=1, pc=self.pathconfig)
        app = buildapp(self.pathconfig)
        app = validator(app)
        self.br = WSGIBrowser(app)

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

    def testMarkup(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
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
        self.assertTrue("Teil&nbsp;#2" in self.get_data())

    def testCourseTitle(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("/.*title$")))
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
        self.assertFalse("Teil&nbsp;#0" in self.get_data())
        self.is_loggedin()

    def testRestorePage(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/.*deadpages$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label="wiederherstellen"))
        self.assertTrue("Teil&nbsp;#0" in self.get_data())
        self.is_loggedin()

    def testAcademyTitle(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("/.*title$")))
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
        form["groups"] = ["cde"]
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Gruppen erfolgreich bearbeitet." in self.get_data())
        form = list(self.br.forms())[1]
        # hack an invalid group
        mechanize_Item(form.find_control("groups"), dict(value="spam"))
        form["groups"] = ["cde", "spam"]
        self.br.open(form.click(label="Speichern und Editieren"))
        self.assertTrue("Nichtexistente Gruppe gefunden!" in self.get_data())
        self.is_loggedin()

    def testCreateCourse(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("/.*createcourse$")))
        form = list(self.br.forms())[1]
        form["name"] = "course03"
        form["title"] = "Testkurs"
        self.br.open(form.click(label=u"Kurs hinzufügen".encode("utf8")))
        self.assertTrue("Area51" in self.get_data())
        self.assertTrue("Testkurs" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("/.*createcourse$")))
        form = list(self.br.forms())[1]
        form["name"] = "foo_bar"
        form["title"] = "next Testkurs"
        self.br.open(form.click(label=u"Kurs hinzufügen".encode("utf8")))
        self.assertTrue("Interner Name nicht wohlgeformt!" in self.get_data())
        self.is_loggedin()

    def testCourseDeletion(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.assertTrue("Area51" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        form = list(self.br.forms())[3]
        self.br.open(form.click(label=u"Kurs löschen".encode("utf8")))
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.assertFalse("Area51" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("deadcourses$")))
        form = list(self.br.forms())[1]
        self.br.open(form.click(label=u"Kurs wiederherstellen".encode("utf8")))
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.assertTrue("Area51" in self.get_data())

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
        mechanize_Item(form.find_control("groups"), dict(value="spam"))
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
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/.*addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.assertTrue("Zugeordnete Bilder" in self.get_data())
        self.assertTrue("#[0] (README-rlog.txt)" in self.get_data())
        self.is_loggedin()

    def testShowBlob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/.*addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/0/$")))
        self.assertTrue("Bildunterschrift/Kommentar: Shiny blob" in self.get_data())
        self.assertTrue("K&uuml;rzel: blob" in self.get_data())
        self.is_loggedin()

    def testMD5Blob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/.*addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/0/.*md5$")))
        self.assertTrue("MD5 Summe des Bildes ist" in self.get_data())
        self.is_loggedin()

    def testEditBlob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/.*addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/0/.*edit$")))
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
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/.*addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        self.assertTrue("Zugeordnete Bilder" in self.get_data())
        self.assertTrue("#[0] (README-rlog.txt)" in self.get_data())
        form = list(self.br.forms())[2]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.assertTrue("Keine Bilder zu diesem Teil gefunden." in self.get_data())
        self.assertFalse("#[0] (README-rlog.txt)" in self.get_data())
        self.is_loggedin()

    def testRestoreBlob(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/.*addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        form.find_control("content").add_file(file("./README-rlog.txt"), filename="README-rlog.txt")
        self.br.open(form.click(label="Bild hochladen"))
        form = list(self.br.forms())[2]
        self.br.open(form.click(label=u"Löschen".encode("utf8")))
        self.assertTrue("Keine Bilder zu diesem Teil gefunden." in self.get_data())
        self.assertFalse("#[0] (README-rlog.txt)" in self.get_data())
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/.*deadblobs$")))
        self.assertTrue("#[0] (README-rlog.txt)" in self.get_data())
        form = list(self.br.forms())[1]
        self.br.open(form.click(label="wiederherstellen"))
        self.assertTrue("Zugeordnete Bilder" in self.get_data())
        self.assertTrue("#[0] (README-rlog.txt)" in self.get_data())
        self.is_loggedin()

    def testAddBlobEmptyLabel(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/.*addblob$")))
        form = list(self.br.forms())[1]
        form["comment"] = "Shiny blob"
        form["label"] = ""
        self.br.open(form.click(label=u"Bild auswählen".encode("utf8")))
        form = list(self.br.forms())[1]
        self.assertTrue(u"Kürzel nicht wohlgeformt!".encode("utf8") in self.get_data())
        self.is_loggedin()

    def testAcademyExport(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(text="Exportieren"))
        self.assertIsTarGz(self.get_data())

    def testRawCourseExport(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course02/$")))
        self.br.open(self.br.click_link(text="Roh-Export"))
        self.assertIsTar(self.get_data())

    def testRawPageExport(self):
        self.br.open(self.url)
        self.do_login()
        self.br.open(self.br.click_link(text="X-Akademie"))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/$")))
        self.br.open(self.br.click_link(url_regex=re.compile("course01/0/$")))
        self.br.open(self.br.click_link(text="rcs"))
        # FIXME: find a better check for a rcs file
        self.assertTrue(self.get_data().startswith("head"))

class SortKeyTests(DfTestCase):
    def verifyBefore(self, after):
        before = Sortkeys.before(after)
        self.assertTrue(before < after, "Sortkeys.before(%s) returned %s" % (after, before))

    def verifyInbetween(self, before, after):
        mid = Sortkeys.between(before, after)
        self.assertTrue(before < mid, "Sortkeys.between(%s, %s) returned %s" % (before, after, mid))
        self.assertTrue(mid < after, "Sortkeys.between(%s, %s) returned %s" % (before, after, mid))

    def testBefore(self):
        self.verifyBefore(['a', 0])
        self.verifyBefore(['asdf', 1, 2, 3])
        self.verifyBefore(['a', -99, 2, 3])

    def testInbetween(self):
        self.verifyInbetween(['a', 0], ['b', 0])
        self.verifyInbetween(['a', 0], ['a', 0, 0])
        self.verifyInbetween(['a', 1], ['a', 1, 1])
        self.verifyInbetween(['a', -1], ['a', -1, -1])
        self.verifyInbetween(['a', 42, 7, 8, 9], ['a', 43])

    def testLegacyOrder(self):
        self.assertTrue(Sortkeys.fromOctets('', legacy='a') < Sortkeys.fromOctets('', legacy='b'))
        self.assertTrue(Sortkeys.fromOctets('', legacy='d') > Sortkeys.fromOctets('', legacy='c'))

    def verifyWriteRead(self, key):
        octets = Sortkeys.toOctets(key)
        readback = Sortkeys.fromOctets(octets)
        self.assertEqual(key, readback)

    def testWriteRead(self):
        self.verifyWriteRead(['a', 0])
        self.verifyWriteRead(['a', 1])
        self.verifyWriteRead(['a', -1])
        self.verifyWriteRead(['aasdf', 1, 2, 3])
        self.verifyWriteRead(['aasdf', 1, 2, 3, 0])
        
class CourseTests(DfTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix=b'dokuforge')
        self.course = Course(os.path.join(self.tmpdir, b'example'))
        
    def tearDown(self):
        shutil.rmtree(self.tmpdir, True)

    def testIsDeletedDefault(self):
        self.assertFalse(self.course.isDeleted)

    def testDelete(self):
        self.course.delete()
        self.assertTrue(self.course.isDeleted)

    def testUnDelete(self):
        self.course.delete()
        self.course.undelete()
        self.assertFalse(self.course.isDeleted)

    def testSetsortkey(self):
        key = ['abc', 47, 11]
        self.course.setSortkey(key)
        self.assertEquals(self.course.sortkey, key)
    

class AcademyTest(DfTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix=b'dokuforge')
        os.makedirs(os.path.join(self.tmpdir, b'example/legacy'))
        self.academy = Academy(os.path.join(self.tmpdir, b'example'), [])
        self.academy.createCourse(u'new01', u'erster neuer Kurs')
        self.academy.createCourse(u'new02', u'zweiter neuer Kurs')
        
    def tearDown(self):
        shutil.rmtree(self.tmpdir, True)

    def assertCourses(self, names):
        """
        Verify the courses, and their order.
        """
        namesfound = [c.name for c in self.academy.listCourses()]
        self.assertEqual(names, namesfound)

    def assertDeadCourses(self, names):
        namesfound = [c.name for c in self.academy.listDeadCourses()]
        self.assertEqual(set(names), set(namesfound))

    def testLegacyCoursePresent(self):
        self.assertCourses([u'legacy', u'new01', u'new02'])
        self.assertDeadCourses([])

    def testDeleteCourse(self):
        self.academy.getCourse(u'new01').delete()
        self.assertCourses([u'legacy', u'new02'])
        self.assertDeadCourses([u'new01'])

    def testDeleteLegacyCourse(self):
        self.academy.getCourse(u'legacy').delete()
        self.assertCourses([u'new01', u'new02'])
        self.assertDeadCourses([u'legacy'])

    def testCourseDeleteUndelete(self):
        self.academy.getCourse(u'new01').delete()
        self.assertDeadCourses([u'new01'])
        self.academy.getCourse(u'new01').undelete()
        self.assertCourses([u'legacy', u'new01', u'new02'])
        self.assertDeadCourses([])

    def testCourseMoveUp(self):
        self.assertCourses([u'legacy', u'new01', u'new02'])
        self.academy.moveUpCourse(u'new01')
        self.assertCourses([u'new01', u'legacy', u'new02'])

    def testCourseMoveUpTop(self):
        self.assertCourses([u'legacy', u'new01', u'new02'])
        self.academy.moveUpCourse(u'new02')
        self.assertCourses([u'legacy', u'new02', u'new01'])
        self.academy.moveUpCourse(u'new02')
        self.assertCourses([u'new02', u'legacy', u'new01'])
        self.academy.moveUpCourse(u'new02')
        self.assertCourses([u'new02', u'legacy', u'new01'])
        
    def testCourseMoveUpSwap(self):
        self.academy.createCourse(u'zzz', u'letzter Kurs')
        self.academy.createCourse(u'yyy', u'vorletzter Kurs')
        self.assertCourses([u'legacy', u'new01', u'new02', u'yyy', u'zzz'])
        self.academy.moveUpCourse(u'yyy')
        self.assertCourses([u'legacy', u'new01', u'yyy', u'new02', u'zzz'])
        self.academy.moveUpCourse(u'new02')
        self.assertCourses([u'legacy', u'new01', u'new02', u'yyy', u'zzz'])
        self.academy.moveUpCourse(u'yyy')
        self.assertCourses([u'legacy', u'new01', u'yyy', u'new02', u'zzz'])
        self.academy.moveUpCourse(u'new02')
        self.assertCourses([u'legacy', u'new01', u'new02', u'yyy', u'zzz'])

class DokuforgeMockTests(DfTestCase):
    def testParserIdempotency(self, rounds=100, minlength=10, maxlength=99):
        for _ in range(rounds):
            for l in range(minlength, maxlength):
                inp = "".join(random.choice("aA \n*[()]1.$<>&\"{}_\\-")
                              for _ in range(l))
                inp2 = dfLineGroupParser(inp).toDF()
                inp3 = dfLineGroupParser(inp2).toDF()
                self.assertEqual(inp2, inp3, "original input was %r" % inp)

    def testParserIdempotency1(self):
        inp = '_a\n[[[\n\n"'
        inp2 = dfLineGroupParser(inp).toDF()
        inp3 = dfLineGroupParser(inp2).toDF()
        self.assertEqual(inp2, inp3)

class DokuforgeMicrotypeUnitTests(DfTestCase):
    def verifyExportsTo(self, df, tex):
        obtained = dfLineGroupParser(df).toTex().strip()
        self.assertEquals(obtained, tex)

    def testQuotes(self):
        self.verifyExportsTo('Wir haben Anf\\"uhrungszeichen "mitten" im Satz.',
                             'Wir haben Anf\\"uhrungszeichen "`mitten"\' im Satz.')
        self.verifyExportsTo('"Am Anfang" ...',
                             '"`Am Anfang"\' \\dots{}')
        self.verifyExportsTo('... "vor Kommata", ...',
                             '\\dots{} "`vor Kommata"\', \\dots{}')
        self.verifyExportsTo('... und "am Ende".',
                             '\\dots{} und "`am Ende"\'.')

    def testAbbrev(self):
        self.verifyExportsTo('Von 3760 v.Chr. bis 2012 n.Chr. und weiter',
                             'Von 3760 v.\\,Chr. bis 2012 n.\\,Chr. und weiter')
        self.verifyExportsTo('Es ist z.B. so, s.o., s.u., etc., dass wir, d.h., der Exporter...',
                             'Es ist z.\\,B. so, s.\\,o., s.\\,u., etc., dass wir, d.\\,h., der Exporter\\dots{}')

    def testAcronym(self):
        self.verifyExportsTo('Bitte ACRONYME anders setzen.',
                             'Bitte \\acronym{ACRONYME} anders setzen.')
        self.verifyExportsTo('Unterscheide T-shirt und DNA-Sequenz.',
                             'Unterscheide T-shirt und \\acronym{DNA}-Sequenz.')

    def testEscaping(self):
        self.verifyExportsTo('Do not allow \\dangerous commands!',
                             'Do not allow \\forbidden\\dangerous commands!')
        self.verifyExportsTo('\\\\ok',
                             '\\\\ok')
        self.verifyExportsTo('\\\\\\bad',
                             '\\\\\\forbidden\\bad')
        self.verifyExportsTo('10% sind ein Zehntel',
                             '10\\% sind ein Zehntel')
        self.verifyExportsTo('f# ist eine Note',
                             'f\# ist eine Note')
        self.verifyExportsTo('$a^b$ ist gut, aber a^b ist schlecht',
                             '$a^b$ ist gut, aber a\\caret{}b ist schlecht')
        self.verifyExportsTo('Heinemann&Co. ist vielleicht eine Firma',
                             'Heinemann\&Co. ist vielleicht eine Firma')
        self.verifyExportsTo('Escaping should also happen in math, like $\\evilmath$, but not $\\mathbb C$',
                             'Escaping should also happen in math, like $\\forbidden\\evilmath$, but not $\\mathbb C$')

    def testEdnoteEscape(self):
        self.verifyExportsTo(
"""

{{

Bobby Tables...

\\end{ednote}

\\herebedragons

}}

""",
"""\\begin{ednote}

Bobby Tables...

|end{ednote}

\\herebedragons

\\end{ednote}""")

if __name__ == '__main__':
    unittest.main()
