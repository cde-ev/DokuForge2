#!/usr/bin/env python
# -*- coding: utf-8 -*-

import gzip
import io
import os
import re
import shutil
import random
import tempfile
import unittest
from wsgiref.validate import validator
import webtest
import datetime

import createexample
from dokuforge import buildapp
from dokuforge.paths import PathConfig
from dokuforge.parser import dfLineGroupParser, dfTitleParser, dfCaptionParser
from dokuforge.common import TarWriter
from dokuforge.common import UTC
from dokuforge.course import Course
from dokuforge.academy import Academy
from dokuforge.user import UserDB
from dokuforge.storage import CachingStorage

try:
    Upload = webtest.Upload
except AttributeError:
    def Upload(filename):
        return (filename,)

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
        self.assertTrue(b"\0\0\0\0\0\0\0\0\0\0" in octets)

    def assertIsTarGz(self, octets):
        f = gzip.GzipFile('dummyfilename', 'rb', 9, io.BytesIO(octets))
        self.assertIsTar(f.read())

class TarWriterTests(DfTestCase):
    def testUncompressed(self):
        timeStampNow = datetime.datetime.utcnow()
        timeStampNow.replace(tzinfo=UTC())
        tarwriter = TarWriter()
        tar = b''
        tar = tar + tarwriter.addChunk(b'myFile', b'contents', timeStampNow)
        tar = tar + tarwriter.close()
        self.assertIsTar(tar)
        
    def testGzip(self):
        timeStampNow = datetime.datetime.utcnow()
        timeStampNow.replace(tzinfo=UTC())
        tarwriter = TarWriter(gzip=True)
        tar = b''
        tar = tar + tarwriter.addChunk(b'myFile', b'contents', timeStampNow)
        tar = tar + tarwriter.close()
        self.assertIsTarGz(tar)

class UserDBTests(DfTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix=u"dokuforge").encode("ascii")
        self.storage = CachingStorage(self.tmpdir, b"db")
        self.userdb = UserDB(self.storage)
        os.makedirs(os.path.join(self.tmpdir, b'aca123/course42'))
        os.makedirs(os.path.join(self.tmpdir, b'aca123/course4711'))
        self.academy = Academy(os.path.join(self.tmpdir, b'aca123'),
                               lambda : [u'abc', u'cde'])
        self.academy.setgroups([u'cde'])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, True)

    def getUser(self, user):
        """
        @type user: unicode
        """
        self.userdb.load()
        return self.userdb.db.get(user)

    def writeUserDbFile(self, contents):
        self.storage.store(contents)

    def testReadSimple(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_view_aca123 True,kurs_read_aca123_course42 True
""")
        user = self.getUser(u"userfoo")
        self.assertTrue(user.allowedRead(self.academy))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse(u'course42')))
        self.assertFalse(user.allowedRead(self.academy, self.academy.getCourse(u'course4711')))

    def testReadRecursive(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_read_aca123 True
""")
        user = self.getUser(u"userfoo")
        self.assertTrue(user.allowedRead(self.academy))
        self.assertTrue(user.allowedRead(self.academy, recursive=True))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse(u'course42')))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse(u'course4711')))

    def testReadNonRecursive(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_view_aca123 True
""")
        user = self.getUser(u"userfoo")
        self.assertFalse(user.allowedRead(self.academy, recursive=True))

    def testReadRevoke(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_read_aca123 True,kurs_read_aca123_course42 False
""")
        user = self.getUser(u"userfoo")
        self.assertTrue(user.allowedRead(self.academy))
        self.assertFalse(user.allowedRead(self.academy, self.academy.getCourse(u'course42')))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse(u'course4711')))

    def testWriteSimple(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = kurs_write_aca123_course42 True
""")
        user = self.getUser(u"userfoo")
        self.assertFalse(user.allowedWrite(self.academy))
        self.assertTrue(user.allowedWrite(self.academy, self.academy.getCourse(u'course42')))
        self.assertFalse(user.allowedWrite(self.academy, self.academy.getCourse(u'course4711')))

    def testWriteRevoke(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_write_aca123 True,kurs_write_aca123_course42 False
""")
        user = self.getUser(u"userfoo")
        self.assertTrue(user.allowedWrite(self.academy))
        self.assertFalse(user.allowedWrite(self.academy, self.academy.getCourse(u'course42')))
        self.assertTrue(user.allowedWrite(self.academy, self.academy.getCourse(u'course4711')))

    def testAdminNonrevokable(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = df_superadmin True,kurs_read_aca123_course42 False,kurs_write_aca123_course4711 False
""")
        user = self.getUser(u"userfoo")
        self.assertTrue(user.allowedRead(self.academy))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse(u'course42')))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse(u'course4711')))
        self.assertTrue(user.allowedWrite(self.academy, self.academy.getCourse(u'course42')))
        self.assertTrue(user.allowedWrite(self.academy, self.academy.getCourse(u'course4711')))

    def testMetaSimple(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_meta_aca123 True
""")
        user = self.getUser(u"userfoo")
        self.assertTrue(user.allowedMeta(self.academy))

    def testMetaGroup(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = gruppe_meta_cde True
""")
        user = self.getUser(u"userfoo")
        self.assertTrue(user.allowedMeta(self.academy))

    def testMetaRevoke(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = gruppe_meta_cde True,akademie_meta_aca123 False
""")
        user = self.getUser(u"userfoo")
        self.assertFalse(user.allowedMeta(self.academy))

    def testGlobalNonRevoke(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = df_meta True,akademie_meta_aca123 False
""")
        user = self.getUser(u"userfoo")
        self.assertTrue(user.allowedMeta(self.academy))

class DokuforgeWebTests(DfTestCase):
    url = "http://www.dokuforge.de"
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix=u"dokuforge").encode("ascii")
        self.pathconfig = PathConfig()
        self.pathconfig.rootdir = self.tmpdir
        createexample.main(size=1, pc=self.pathconfig)
        app = buildapp(self.pathconfig)
        app = validator(app)
        self.app = webtest.TestApp(app)
        self.res = None

    def tearDown(self):
        shutil.rmtree(self.tmpdir, True)

    def do_login(self, username="bob", password="secret"):
        self.res = self.app.get("/")
        # raises TypeError if there is more than one form
        form = self.res.form
        form["username"] = username
        form["password"] = password
        self.res = form.submit("submit")

    def do_logout(self):
        form = self.res.form
        self.res = form.submit("submit")

    def is_loggedin(self):
        self.res.mustcontain("/logout")

    def testLogin(self):
        self.do_login()
        self.is_loggedin()

    def testLoginFailedUsername(self):
        self.do_login(username="nonexistent")
        # FIXME: sane error message
        self.assertEqual(self.res.body, b"wrong password")

    def testLoginFailedPassword(self):
        self.do_login(password="wrong")
        self.assertEqual(self.res.body, b"wrong password")

    def testLoginClick(self):
        self.do_login()
        self.res = self.res.click(description="DokuForge")
        self.is_loggedin()

    def testLogout(self):
        self.do_login()
        self.do_logout()
        self.res.mustcontain(no="/logout")

    def testAcademy(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.is_loggedin()
        self.res.mustcontain("Exportieren")

    def testCourse(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.is_loggedin()
        self.res.mustcontain("df2-Rohdaten")

    def testPage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.is_loggedin()
        self.res.mustcontain("neues Bild hinzuf")

    def testEdit(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        for (inputstr, outputstr) in teststrings:
            self.res = self.res.click(description="Editieren")
            form = self.res.forms[1]
            form["content"] = inputstr
            self.res = form.submit(name="saveshow")
            self.res.mustcontain(outputstr)
        self.is_loggedin()

    def testMarkup(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(description="Editieren")
        form = self.res.forms[1]
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
        self.res = form.submit(name="saveshow")
        self.res.mustcontain("$\\sqrt{2}$", "ednote \\end{ednote}")
        self.is_loggedin()

    def testMovePage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        form = self.res.forms[1]
        self.res = form.submit()
        self.is_loggedin()

    def testCreatePage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        form = self.res.forms[2]
        self.res = form.submit()
        self.is_loggedin()
        self.res.mustcontain("Teil&nbsp;#2")

    def testCourseTitle(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("/.*title$"))
        for (inputstr, outputstr) in teststrings:
            form = self.res.forms[1]
            form["content"] = inputstr
            self.res = form.submit(name="saveedit")
            self.res.mustcontain(outputstr)
        self.is_loggedin()

    def testDeletePage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        form = self.res.forms[1]
        self.res = form.submit()
        self.res.mustcontain(no="Teil&nbsp;#0")
        self.is_loggedin()

    def testRestorePage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        form = self.res.forms[1]
        self.res = form.submit()
        self.res = self.res.click(href=re.compile("course01/.*deadpages$"))
        form = self.res.forms[1]
        self.res = form.submit()
        self.res.mustcontain("Teil&nbsp;#0")
        self.is_loggedin()

    def testAcademyTitle(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("/.*title$"))
        for (inputstr, outputstr) in teststrings:
            form = self.res.forms[1]
            form["content"] = inputstr
            self.res = form.submit(name="saveedit")
            self.res.mustcontain(outputstr)
        self.is_loggedin()

    def testAcademyGroups(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(description="Gruppen bearbeiten")
        form = self.res.forms[1]
        form["groups"] = ["cde"]
        self.res = form.submit(name="saveedit")
        self.res.mustcontain("Gruppen erfolgreich bearbeitet.")
        form = self.res.forms[1]
        form["groups"].force_value(["cde", "spam"])
        self.res = form.submit(name="saveedit")
        self.res.mustcontain("Nichtexistente Gruppe gefunden!")
        self.is_loggedin()

    def testCreateCourse(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("/.*createcourse$"))
        form = self.res.forms[1]
        form["name"] = "course03"
        form["title"] = "Testkurs"
        self.res = form.submit()
        self.res.mustcontain("Area51", "Testkurs")
        self.res = self.res.click(href=re.compile("/.*createcourse$"))
        form = self.res.forms[1]
        form["name"] = "foo_bar"
        form["title"] = "next Testkurs"
        self.res = form.submit()
        self.res.mustcontain("Interner Name nicht wohlgeformt!")
        self.is_loggedin()

    def testCourseDeletion(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res.mustcontain("Area51")
        self.res = self.res.click(href=re.compile("course01/$"))
        form = self.res.forms[3]
        self.res = form.submit()
        self.res = self.res.click(description="X-Akademie")
        self.res.mustcontain(no="Area51")
        self.res = self.res.click(href=re.compile("deadcourses$"))
        form = self.res.forms[1]
        self.res = form.submit()
        self.res = self.res.click(description="X-Akademie")
        self.res.mustcontain("Area51")

    def testCreateAcademy(self):
        self.do_login()
        self.res = self.res.click(href=re.compile("/createacademy$"))
        form = self.res.forms[1]
        form["name"] = "newacademy-2001"
        form["title"] = "Testakademie"
        form["groups"] = ["cde"]
        self.res = form.submit()
        self.res.mustcontain("Testakademie", "X-Akademie")
        self.res = self.res.click(href=re.compile("/createacademy$"))
        form = self.res.forms[1]
        form["name"] = "foo_bar"
        form["title"] = "next Testakademie"
        form["groups"] = ["cde"]
        self.res = form.submit()
        self.res.mustcontain("Interner Name nicht wohlgeformt!")
        form = self.res.forms[1]
        form["name"] = "foobar"
        form["title"] = "next Testakademie"
        form["groups"].force_value(["cde", "spam"])
        self.res = form.submit()
        self.res.mustcontain("Nichtexistente Gruppe gefunden!")
        self.is_loggedin()

    def testGroups(self):
        self.do_login()
        self.res = self.res.click(href=re.compile("/groups/$"))
        form = self.res.forms[1]
        form["content"] = """[cde]
title = CdE-Akademien

[spam]
title = Wie der Name sagt
"""
        self.res = form.submit(name="saveedit")
        self.res.mustcontain("Aenderungen erfolgreich gespeichert.")
        form = self.res.forms[1]
        form["content"] = """[cde]
title = CdE-Akademien

[spam
title = Wie der Name sagt
"""
        self.res = form.submit(name="saveedit")
        self.res.mustcontain("Es ist ein allgemeiner Parser-Fehler aufgetreten!")
        self.is_loggedin()

    def testAdmin(self):
        self.do_login()
        self.res = self.res.click(href=re.compile("/admin/$"))
        form = self.res.forms[1]
        form["content"] = """[bob]
name = bob
status = ueberadmin
password = secret
permissions = df_superadmin True,df_admin True
"""
        self.res = form.submit(name="saveedit")
        self.res.mustcontain("Aenderungen erfolgreich gespeichert.")
        form = self.res.forms[1]
        form["content"] = """[bob
name = bob
status = ueberadmin
password = secret
permissions = df_superadmin True,df_admin True
"""
        self.res = form.submit(name="saveedit")
        self.res.mustcontain("Es ist ein allgemeiner Parser-Fehler aufgetreten!")
        self.is_loggedin()

    def testStyleguide(self):
        self.res = self.app.get("/")
        self.res = self.res.click(href=re.compile("/style/$"))
        self.res.mustcontain("Hier erfährst du, was bei der Eingabe der Texte in DokuForge")
        self.res = self.res.click(href=re.compile("/style/grundlagen$"))
        self.res.mustcontain("Bedienung von DokuForge")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/abbildungen$"))
        self.res.mustcontain(u"Abbildungen")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/mathe$"))
        self.res.mustcontain("Mathematik-Umgebung")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/gedichte$"))
        self.res.mustcontain(u"Gedichte")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/literatur$"))
        self.res.mustcontain(u"Literatur")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/tabellen$"))
        self.res.mustcontain(u"Tabellen")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/konflikte$"))
        self.res.mustcontain(u"Konflikte")
        self.res = self.res.click(description="Login")
        self.do_login()
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res.mustcontain("Hier erfährst du, was bei der Eingabe der Texte in DokuForge")
        self.res = self.res.click(href=re.compile("/style/grundlagen$"))
        self.res.mustcontain("Bedienung von DokuForge")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/abbildungen$"))
        self.res.mustcontain(u"Abbildungen")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/mathe$"))
        self.res.mustcontain("Mathematik-Umgebung")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/gedichte$"))
        self.res.mustcontain(u"Gedichte")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/literatur$"))
        self.res.mustcontain(u"Literatur")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/tabellen$"))
        self.res.mustcontain(u"Tabellen")
        self.res = self.res.click(href=re.compile("/style/$"), index=0)
        self.res = self.res.click(href=re.compile("/style/konflikte$"))
        self.res.mustcontain(u"Konflikte")
        self.is_loggedin()

    def testAddBlob(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(href=re.compile("course01/0/.*addblob$"))
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.res = form.submit()
        form = self.res.forms[1]
        form["content"] = Upload("README-rlog.txt")
        self.res = form.submit()
        self.res.mustcontain("Zugeordnete Bilder", "#[0] (README-rlog.txt)")
        self.is_loggedin()

    def testShowBlob(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(href=re.compile("course01/0/.*addblob$"))
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.res = form.submit()
        form = self.res.forms[1]
        form["content"] = Upload("README-rlog.txt")
        self.res = form.submit()
        self.res = self.res.click(href=re.compile("course01/0/0/$"))
        self.res.mustcontain("Bildunterschrift/Kommentar: Shiny blob",
                             "K&uuml;rzel: blob")
        self.is_loggedin()

    def testMD5Blob(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(href=re.compile("course01/0/.*addblob$"))
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.res = form.submit()
        form = self.res.forms[1]
        form["content"] = Upload("README-rlog.txt")
        self.res = form.submit()
        self.res = self.res.click(href=re.compile("course01/0/0/$"))
        self.res = self.res.click(href=re.compile("course01/0/0/.*md5$"))
        self.res.mustcontain("MD5 Summe des Bildes ist")
        self.is_loggedin()

    def testEditBlob(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(href=re.compile("course01/0/.*addblob$"))
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.res = form.submit()
        form = self.res.forms[1]
        form["content"] = Upload("README-rlog.txt")
        self.res = form.submit()
        self.res = self.res.click(href=re.compile("course01/0/0/$"))
        self.res = self.res.click(href=re.compile("course01/0/0/.*edit$"))
        form = self.res.forms[1]
        form["comment"] = "Real Shiny blob"
        form["label"] = "blub"
        form["name"] = "README"
        self.res = form.submit()
        self.res.mustcontain("Bildunterschrift/Kommentar: Real Shiny blob",
                             "K&uuml;rzel: blub",
                             "Dateiname: README")
        self.is_loggedin()

    def testDeleteBlob(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(href=re.compile("course01/0/.*addblob$"))
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.res = form.submit()
        form = self.res.forms[1]
        form["content"] = Upload("README-rlog.txt")
        self.res = form.submit()
        self.res.mustcontain("Zugeordnete Bilder", "#[0] (README-rlog.txt)")
        form = self.res.forms[2]
        self.res = form.submit()
        self.res.mustcontain("Keine Bilder zu diesem Teil gefunden.",
                             no="#[0] (README-rlog.txt)")
        self.is_loggedin()

    def testRestoreBlob(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(href=re.compile("course01/0/.*addblob$"))
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.res = form.submit()
        form = self.res.forms[1]
        form["content"] = Upload("README-rlog.txt")
        self.res = form.submit()
        form = self.res.forms[2]
        self.res = form.submit()
        self.res.mustcontain("Keine Bilder zu diesem Teil gefunden.",
                             no="#[0] (README-rlog.txt)")
        self.res = self.res.click(href=re.compile("course01/0/.*deadblobs$"))
        self.res.mustcontain("#[0] (README-rlog.txt)")
        form = self.res.forms[1]
        self.res = form.submit()
        self.res.mustcontain("Zugeordnete Bilder", "#[0] (README-rlog.txt)")
        self.is_loggedin()

    def testAddBlobEmptyLabel(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(href=re.compile("course01/0/.*addblob$"))
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = ""
        self.res = form.submit()
        form = self.res.forms[1]
        self.res.mustcontain(u"Kürzel nicht wohlgeformt!")
        self.is_loggedin()

    def testAcademyExport(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(description="Exportieren")
        self.assertIsTarGz(self.res.body)

    def testRawCourseExport(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course02/$"))
        self.res = self.res.click(description="df2-Rohdaten")
        self.assertIsTarGz(self.res.body)

    def testRawPageExport(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href=re.compile("course01/$"))
        self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
        self.res = self.res.click(description="rcs")
        # FIXME: find a better check for a rcs file
        self.assertTrue(self.res.body.startswith(b"head"))

class CourseTests(DfTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix=u"dokuforge").encode("ascii")
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

class AcademyTest(DfTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix=u'dokuforge').encode("ascii")
        os.makedirs(os.path.join(self.tmpdir, b'example/legacy'))
        self.academy = Academy(os.path.join(self.tmpdir, b'example'), [])
        self.academy.createCourse(u'new01', u'erster neuer Kurs')
        self.academy.createCourse(u'new02', u'zweiter neuer Kurs')
        
    def tearDown(self):
        shutil.rmtree(self.tmpdir, True)

    def assertCourses(self, names):
        namesfound = [c.name for c in self.academy.listCourses()]
        self.assertEqual(set(names), set(namesfound))

    def assertDeadCourses(self, names):
        namesfound = [c.name for c in self.academy.listDeadCourses()]
        self.assertEqual(set(names), set(namesfound))

    def testLegacyCoursePresent(self):
        self.assertCourses([b'legacy', b'new01', b'new02'])
        self.assertDeadCourses([])

    def testDeleteCourse(self):
        self.academy.getCourse(u'new01').delete()
        self.assertCourses([b'legacy', b'new02'])
        self.assertDeadCourses([b'new01'])

    def testDeleteLegacyCourse(self):
        self.academy.getCourse(u'legacy').delete()
        self.assertCourses([b'new01', b'new02'])
        self.assertDeadCourses([b'legacy'])

    def testCourseDeleteUndelete(self):
        self.academy.getCourse(u'new01').delete()
        self.assertDeadCourses([b'new01'])
        self.academy.getCourse(u'new01').undelete()
        self.assertCourses([b'legacy', b'new01', b'new02'])
        self.assertDeadCourses([])

class DokuforgeMockTests(DfTestCase):
    def verify_idempotency(self, inp):
        inp2 = dfLineGroupParser(inp).toDF()
        inp3 = dfLineGroupParser(inp2).toDF()
        self.assertEqual(inp2, inp3, "original input was %r" % inp)

    def testParserIdempotency(self, rounds=100, minlength=10, maxlength=99):
        for _ in range(rounds):
            for l in range(minlength, maxlength):
                inp = u"".join(random.choice(u"aA \n*[()]1.$<>&\"{}_\\-")
                              for _ in range(l))
                self.verify_idempotency(inp)

    def testParserIdempotency1(self):
        self.verify_idempotency(u'_a\n[[[\n\n"')

    def testHeadingHtmlEscape(self):
        out = dfLineGroupParser(u"[bad < html chars >]").toHtml().strip()
        self.assertEqual(out, u"<h1>bad &lt; html chars &gt;</h1>")

    def testAuthorHtmlEscape(self):
        out = dfLineGroupParser(u"[ok]\n(bad < author >)").toHtml().strip()
        self.assertEqual(out, u"<h1>ok</h1>\n<i>bad &lt; author &gt;</i>")

class DokuforgeMicrotypeUnitTests(DfTestCase):
    def verifyExportsTo(self, df, tex):
        obtained = dfLineGroupParser(df).toTex().strip()
        self.assertEqual(obtained, tex)

    def testItemize(self):
        self.verifyExportsTo(u'- Text',
                             u'\\begin{itemize}\n\\item Text\n\\end{itemize}')
        self.verifyExportsTo(u'-Text', u'-Text')


    def testQuotes(self):
        self.verifyExportsTo(u'Wir haben Anf\\"uhrungszeichen "mitten" im Satz.',
                             u'Wir haben Anf\\"uhrungszeichen "`mitten"\' im Satz.')
        self.verifyExportsTo(u'"Am Anfang" ...',
                             u'"`Am Anfang"\' \\dots{}')
        self.verifyExportsTo(u'... "vor Kommata", ...',
                             u'\\dots{} "`vor Kommata"\', \\dots{}')
        self.verifyExportsTo(u'... und "am Ende".',
                             u'\\dots{} und "`am Ende"\'.')
        self.verifyExportsTo(u'"Vor und"\n"nach" Zeilenumbrüchen.',
                             u'"`Vor und"\' "`nach"\' Zeilenumbrüchen.')

    def testAbbrev(self):
        self.verifyExportsTo(u'Von 3760 v.Chr. bis 2012 n.Chr. und weiter',
                             u'Von 3760 v.\\,Chr. bis 2012 n.\\,Chr. und weiter')
        self.verifyExportsTo(u'Es ist z.B. so, s.o., s.u., etc., dass wir, d.h., er...',
                             u'Es ist z.\\,B. so, s.\\,o., s.\\,u., etc., dass wir, d.\\,h., er\\dots{}')

    def testAcronym(self):
        self.verifyExportsTo(u'Bitte ACRONYME anders setzen.',
                             u'Bitte \\acronym{ACRONYME} anders setzen.')
        self.verifyExportsTo(u'Unterscheide T-shirt und DNA-Sequenz.',
                             u'Unterscheide T-shirt und \\acronym{DNA}-Sequenz.')

    def testEscaping(self):
        self.verifyExportsTo(u'Do not allow \\dangerous commands!',
                             u'Do not allow \\forbidden\\dangerous commands!')
        self.verifyExportsTo(u'\\\\ok',
                             u'\\\\ok')
        self.verifyExportsTo(u'\\\\\\bad',
                             u'\\\\\\forbidden\\bad')
        self.verifyExportsTo(u'10% sind ein Zehntel',
                             u'10\\% sind ein Zehntel')
        self.verifyExportsTo(u'f# ist eine Note',
                             u'f\# ist eine Note')
        self.verifyExportsTo(u'$a^b$ ist gut, aber a^b ist schlecht',
                             u'$a^b$ ist gut, aber a\\caret{}b ist schlecht')
        self.verifyExportsTo(u'Heinemann&Co. ist vielleicht eine Firma',
                             u'Heinemann\&Co. ist vielleicht eine Firma')
        self.verifyExportsTo(u'Escaping in math: $\\evilmath$, but $\\mathbb C$',
                             u'Escaping in math: $\\forbidden\\evilmath$, but $\\mathbb C$')

    def testTrails(self):
        self.verifyExportsTo(u'trailing space ',
                             u'trailing space')
        self.verifyExportsTo(u'trailing backslash \\',
                             u'trailing backslash \\@\\textbackslash{}')

    def testEdnoteEscape(self):
        self.verifyExportsTo(
u"""

{{

Bobby Tables...

\\end{ednote}

\\herebedragons

}}

""",
u"""\\begin{ednote}

Bobby Tables...

|end{ednote}

\\herebedragons

\\end{ednote}""")

    def testStructures(self):
        self.verifyExportsTo(u'[foo]\n(bar)',
                             u'\\section{foo}\n\\authors{bar}')
        self.verifyExportsTo(u'[[foo]]\n\n(bar)',
                             u'\\subsection{foo}\n\n(bar)')
        self.verifyExportsTo(u'- item\n\n-nonitem',
                             u'\\begin{itemize}\n\\item item\n\end{itemize}\n\n-nonitem')
        self.verifyExportsTo(u'1. item',
                             u'\\begin{enumerate}\n% 1\n\\item item\n\end{enumerate}')
    def testNumeralScope(self):
        self.verifyExportsTo(u'10\xb3 Meter sind ein km',
                             u'10\xb3 Meter sind ein km')

class DokuforgeTitleParserTests(DfTestCase):
    def verifyExportsTo(self, df, tex):
        obtained = dfTitleParser(df).toTex().strip()
        self.assertEqual(obtained, tex)

    def testEscaping(self):
        self.verifyExportsTo(u'Do not allow \\dangerous commands!',
                             u'Do not allow \\forbidden\\dangerous commands!')
        self.verifyExportsTo(u'\\\\ok',
                             u'\\\\ok')
        self.verifyExportsTo(u'\\\\\\bad',
                             u'\\\\\\forbidden\\bad')
        self.verifyExportsTo(u'10% sind ein Zehntel',
                             u'10\\% sind ein Zehntel')
        self.verifyExportsTo(u'f# ist eine Note',
                             u'f\# ist eine Note')
        self.verifyExportsTo(u'$a^b$ ist gut, aber a^b ist schlecht',
                             u'$a^b$ ist gut, aber a\\caret{}b ist schlecht')
        self.verifyExportsTo(u'Heinemann&Co. ist vielleicht eine Firma',
                             u'Heinemann\&Co. ist vielleicht eine Firma')
        self.verifyExportsTo(u'Escaping in math: $\\evilmath$, but $\\mathbb C$',
                             u'Escaping in math: $\\forbidden\\evilmath$, but $\\mathbb C$')

class DokuforgeCaptionParserTests(DfTestCase):
    def verifyExportsTo(self, df, tex):
        obtained = dfTitleParser(df).toTex().strip()
        self.assertEqual(obtained, tex)

    def testEscaping(self):
        self.verifyExportsTo(u'Do not allow \\dangerous commands!',
                             u'Do not allow \\forbidden\\dangerous commands!')
        self.verifyExportsTo(u'\\\\ok',
                             u'\\\\ok')
        self.verifyExportsTo(u'\\\\\\bad',
                             u'\\\\\\forbidden\\bad')
        self.verifyExportsTo(u'10% sind ein Zehntel',
                             u'10\\% sind ein Zehntel')
        self.verifyExportsTo(u'f# ist eine Note',
                             u'f\# ist eine Note')
        self.verifyExportsTo(u'$a^b$ ist gut, aber a^b ist schlecht',
                             u'$a^b$ ist gut, aber a\\caret{}b ist schlecht')
        self.verifyExportsTo(u'Heinemann&Co. ist vielleicht eine Firma',
                             u'Heinemann\&Co. ist vielleicht eine Firma')
        self.verifyExportsTo(u'Escaping in math: $\\evilmath$, but $\\mathbb C$',
                             u'Escaping in math: $\\forbidden\\evilmath$, but $\\mathbb C$')

if __name__ == '__main__':
    unittest.main()
