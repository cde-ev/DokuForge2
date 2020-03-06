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
import tarfile

import createexample
from dokuforge import buildapp
from dokuforge.paths import PathConfig
from dokuforge.parser import dfLineGroupParser, dfTitleParser, dfCaptionParser, Estimate
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
        self.res.mustcontain("Testexport")

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
            self.res = self.res.click(description="Editieren", index=0)
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
        self.res = self.res.click(description="Editieren", index=1)
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

    def testAddDifferentImageBlobs(self):
        imageFilenamesUnchanged = ['fig_platzhalter.jpg',
                                   'fig_platzhalter.png',
                                   'Fuzzi-Hut-Logo.eps',
                                   'Fuzzi-Hut-Logo2.EPS',
                                   'Fuzzi-Hut-Logo.pdf',
                                   'Fuzzi-Hut-Logo.Komisch-pdf',
                                   'Fuzzi-Hut-Logo.svg',
                                   'Fuzzi-Hut-Logo2.SVG']

        # note that fig_platzhalter2.jpg will not become duplicate in export
        # as it gets prefixed by blob_#
        imageFilenamesToBeChanged = {'fig_platzhalter.jpeg'  : 'fig_platzhalter.jpg'  ,
                                     'fig_platzhalter2.JPEG' : 'fig_platzhalter2.jpg' ,
                                     'fig_platzhalter2.JPG'  : 'fig_platzhalter2.jpg' ,
                                     'fig_platzhalter2.PNG'  : 'fig_platzhalter2.png' ,
                                     'Fuzzi-Hut-Logo2.PDF'   : 'Fuzzi-Hut-Logo2.pdf'   }

        imageFilenames = imageFilenamesUnchanged + imageFilenamesToBeChanged.keys()

        self.do_login()
        os.chdir('testData')
        counter=0 # to achieve distinct labels
        for imageFilename in imageFilenames:
            self.res = self.res.click(description="X-Akademie")
            self.res = self.res.click(href=re.compile("course01/$"))
            self.res = self.res.click(href=re.compile("course01/0/$"), index=0)
            self.res = self.res.click(href=re.compile("course01/0/.*addblob$"))
            form = self.res.forms[1]
            form["comment"] = "Kommentar"
            form["label"] = "blob"+str(counter)
            self.res = form.submit()
            form = self.res.forms[1]
            form["content"] = Upload(imageFilename)
            self.res = form.submit()
            counter = counter+1
        os.chdir('..')

        expectedFilenamesInExport = imageFilenamesUnchanged + imageFilenamesToBeChanged.values()

        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(description="Exportieren")
        tarFile = tarfile.open(mode='r',fileobj=io.BytesIO(self.res.body))
        memberNames = tarFile.getnames()
        filenamesInExport = []
        for m in memberNames:
            filenamesInExport.append( m.split('/')[-1] )

        # check if all expected file names are present
        # note that they are prefixed by blob_#_ when exporting
        allFound = True
        for expectedFilename in expectedFilenamesInExport:
            found = False
            for f in filenamesInExport:
                if f.endswith(expectedFilename):
                    found = True
            allFound &= found

        self.assertTrue(allFound)

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
        form = self.res.forms[3]
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
        form = self.res.forms[3]
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
        self.res = self.res.click(description="Testexport")
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
        self.res = self.res.click(description="rcs", index=0)
        # FIXME: find a better check for a rcs file
        self.assertTrue(self.res.body.startswith(b"head"))

    def testPartDeletion(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res.mustcontain("Area51")
        self.res = self.res.click(href=re.compile("/.*createcourse$"))
        form = self.res.forms[1]
        form["name"] = "bug"
        form["title"] = "bug"
        self.res = form.submit()
        self.res.mustcontain("Area51", "bug")
        self.res = self.res.click(href=re.compile("/bug/$"))
        self.res = self.res.forms[1].submit() # create new part
        self.res = self.res.click(href=re.compile("/bug/0/$"), index=0)
        self.res = self.res.forms[1].submit() # delete only part

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

class ExporterTestStrings:
    """
    Input and expected output for testing exporter.
    """

    itemizeAndCo = [[u'- Text',
                     u'\\begin{itemize}\n\\item Text\n\\end{itemize}'],
                    [u'-Text',
                     u'-Text'],
                    [u'- item\n\n-nonitem',
                     u'\\begin{itemize}\n\\item item\n\end{itemize}\n\n-nonitem'],
                    [u'1. item',
                     u'\\begin{enumerate}\n% 1\n\\item item\n\end{enumerate}'] ]

    quotes = [ [u'Wir haben Anf\\"uhrungszeichen "mitten" im Satz.',
                u'Wir haben Anf\\"uhrungszeichen "`mitten"\' im Satz.'],
               [u'"Am Anfang" des Texts',
                u'"`Am Anfang"\' des Texts'],
               [u'in der Mitte "vor Kommata", im Text',
                u'in der Mitte "`vor Kommata"\', im Text'],
               [u'und "am Ende".',
                u'und "`am Ende"\'.'],
               [u'"Vor und"\n"nach" Zeilenumbrüchen.',
                u'"`Vor und"\' "`nach"\' Zeilenumbrüchen.'],
               [u'Markus\' single quote',
                u'Markus\\@\' single quote'],
               [u'"Wow"-Effekt',
                u'"`Wow"\'-Effekt'],
               [u'Was laesst Menschen "aufbluehen"?',
                u'Was laesst Menschen "`aufbluehen"\'?'],
               [u'ei "(Ei" ei ("Ei" ei',
                u'ei "`(Ei"\' ei ("`Ei"\' ei'],
               [u'"Schoki"! "Cola"; "Wasser", "Nudeln": "Suppe")',
                u'"`Schoki"\'! "`Cola"\'; "`Wasser"\', "`Nudeln"\': "`Suppe"\')'],
               [u'"Yo!" "Whaaat?" "Boom." "Cola;" "Nudeln:" "Suppe)"',
                u'"`Yo!"\' "`Whaaat?"\' "`Boom."\' "`Cola;"\' "`Nudeln:"\' "`Suppe)"\''],
               [u'"Wasser,"',
                u'"`Wasser,"\''],
               [u'So "sollte es" sein. Und "$so$ ist $es$" hier.',
                u'So "`sollte es"\' sein. Und \\@"`$so$ ist $es$\\@"\' hier.'],
               [u'Bitte "ACRONYME" berücksichtigen.',
                u'Bitte "`\\@\\acronym{ACRONYME}"\' berücksichtigen.'],
               [u'"Altern der DNA"',
                u'"`Altern der \\@\\acronym{DNA}"\''] ]

    abbreviation = [ [u'Von 3760 v.Chr. bis 2012 n.Chr. und weiter',
                      u'Von 3760\,v.\\,Chr. bis 2012\,n.\\,Chr. und weiter'],
                     [u'Es ist z.B. so, s.o., s.u., etc., dass wir, d.h.',
                      u'Es ist z.\\,B. so, s.\\,o., s.\\,u., etc., dass wir, d.\\,h.'],
                     [u'aber u.a. auch o.ä. wie o.Ä.',
                      u'aber u.\\,a. auch o.\\,ä. wie o.\\,Ä.'],
                     [u'Keine erlaubet Abkuerzungen sind umgspr. und oBdA. im Exporter.',
                      u'Keine erlaubet Abkuerzungen sind umgspr. und oBdA. im Exporter.'],
                     # similar to above, but with spaces in input
                     [u'Von 3760 v. Chr. bis 2012 n. Chr. und weiter',
                      u'Von 3760\,v.\\,Chr. bis 2012\,n.\\,Chr. und weiter'],
                     [u'Es ist z. B. so, s. o., s. u., etc., dass wir,',
                      u'Es ist z.\\,B. so, s.\\,o., s.\\,u., etc., dass wir,'],
                     [u'd. h., der Exporter bzw. oder ca. oder so.',
                      u'd.\\,h., der Exporter bzw. oder ca. oder so.'],
                     [u'Aber u. a. auch o. ä. wie o. Ä.',
                      u'Aber u.\\,a. auch o.\\,ä. wie o.\\,Ä.']]

    acronym = [ [u'Bitte ACRONYME wie EKGs anders setzen.',
                 u'Bitte \\@\\acronym{ACRONYME} wie \\@\\acronym{EKGs} anders setzen.'],
                [u'Unterscheide T-shirt und DNA-Sequenz.',
                 u'Unterscheide T-shirt und \\@\\acronym{DNA}-Sequenz.'],
                [u'Wenn 1D nicht reicht, nutze 2D oder 6D.',
                 u'Wenn 1\\@\\acronym{D} nicht reicht, nutze 2\\@\\acronym{D} oder\n6\\@\\acronym{D}.'],
                [u'Wahlergebnis fuer die SPD: 9% (NRW).',
                 u'Wahlergebnis fuer die \\@\\acronym{SPD}: 9\\,\\% (\\@\\acronym{NRW}).'],
                [u'FDP? CDU! CSU. ÖVP.',
                 u'\\@\\acronym{FDP}? \\@\\acronym{CDU}! \\@\\acronym{CSU}. \\@\\acronym{ÖVP}.'],
                [u'Das ZNS.',
                 u'Das \\@\\acronym{ZNS}.'] ]

    escaping = [ [u'Forbid \\mathbb and \\dangerous outside math.',
                  u'Forbid \\@\\forbidden\\mathbb and \\@\\forbidden\\dangerous outside math.'],
                 [u'Do not allow $a \\dangerous{b}$ commands!',
                  u'Do not allow $a \\@\\forbidden\\dangerous{b}$ commands!'],
                 [u'\\\\ok, $\\\\ok$',
                  u'\\\\ok, $\\\\ok$'],
                 [u'$\\\\\\bad$',
                  u'$\\\\\\@\\forbidden\\bad$'],
                 [u'Escaping in math like $\\evilmath$, but not $\\mathbb C$',
                  u'Escaping in math like $\\@\\forbidden\\evilmath$, but not $\\mathbb C$'],
                 [u'$\\circ$ $\\cap\\inf$ $\\times$',
                  u'$\\circ$ $\\cap\\inf$ $\\times$' ],
                 [u'$a &= b$',
                  u'$a \\@\\forbidden\\&= b$'],
                 [u'$$a &= b$$',
                  u'\\begin{equation*}\na \\@\\forbidden\\&= b\n\\end{equation*}'],
                 [u'Trailing \\',
                  u'Trailing \\@\\backslash'],
                 [u'$Trailing \\$',
                  u'$Trailing \\@\\backslash$'],
                 [u'f# ist eine Note',
                  u'f\\@\\# ist eine Note'],
                 [u'$a^b$ ist gut, aber a^b ist schlecht',
                  u'$a^b$ ist gut, aber a\\@\\caret{}b ist schlecht'],
                 [u'Heinemann&Co. ist vielleicht eine Firma',
                  u'Heinemann\\@\\&Co. ist vielleicht eine Firma'],
                 [u'10% sind ein Zehntel und mehr als 5 %.',
                  u'10\\,\\% sind ein Zehntel und mehr als 5\\@\\,\\%.'],
                 [u'Geschweifte Klammern { muessen } escaped werden.',
                  u'Geschweifte Klammern \\@\\{ muessen \\@\\} escaped werden.'],
                 [u'Tilde~ist unklar. $Auch~hier$.',
                  u'Tilde\\@~ist unklar. $Auch\\@~hier$.'] ]

    mathEnvironments = [ [u'b $$\\circ \\cap \\inf \\times$$ e',
                          u'b\n\\begin{equation*}\n\\circ \\cap \\inf \\times\n\\end{equation*}\n e'],
                         [u'b $$\n\\circ \\cap \\inf \\times\n$$ e',
                          u'b\n\\begin{equation*}\n\\circ \\cap \\inf \\times\n\\end{equation*}\n e'],
                         [u'b $$\n\\begin{equation}a + b = c\\end{equation}\n$$ e',
                          u'b\n\\begin{equation}\na + b = c\n\\end{equation}\n e'],
                         [u'b $$\n\\begin{equation*}a + b = c \\end{equation*}\n$$ e',
                          u'b\n\\begin{equation*}\na + b = c\n\\end{equation*}\n e'],
                         [u'b $$\n\\begin{align}\na + b &= c \\\\\na - b &= d\n\\end{align}\n$$ e',
                          u'b\n\\begin{align}\na + b &= c \\\\\na - b &= d\n\\end{align}\n e'],
                         [u'b $$\n\\begin{align*}\na + b &= c \\\\\na - b &= d\n\\end{align*}\n$$ e',
                          u'b\n\\begin{align*}\na + b &= c \\\\\na - b &= d\n\\end{align*}\n e'],
                         [u'b $$\n\\begin{align}\nabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz &= c\\\\\nabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz &= d \\end{align}\n$$ e',
                          u'b\n\\begin{align}\nabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz &= c\\\\\nabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz &= d\n\\end{align}\n e'],
                         [u'a $$\n\\begin{equation} b &= c \\end{equation}\n$$ d',
                          u'a\n\\begin{equation}\nb \\@\\forbidden\\&= c\n\\end{equation}\n d'],
                         [u'b $$\n\\begin{equation}a + b &= c\\end{equation}\n$$ e',
                          u'b\n\\begin{equation}\na + b \\@\\forbidden\\&= c\n\\end{equation}\n e'],
                         [u'b $$\n\\begin{align}a + b \evilmath = c\\end{align}\n$$ e',
                          u'b\n\\begin{align}\na + b \\@\\forbidden\\evilmath = c\n\\end{align}\n e'],
                         [u'Bla $$\n\\begin{align}\na + b &= c\\\\\na - b &= d \\end{align}\n$$ Blub',
                          u'Bla\n\\begin{align}\na + b &= c\\\\\na - b &= d\n\\end{align}\n Blub'],
                         [u'Matrix $\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}$.',
                          u'Matrix $\\@\\forbidden\\begin{pmatrix} a \\@\\forbidden\\& b \\\\ c\n\\@\\forbidden\\& d \\@\\forbidden\\end{pmatrix}$.'] ]

    evilUTF8 = [ [u'Bla … blub bloink.',
                  u'Bla~\\@\\dots{} blub bloink.'],
                 [u'Bla – blub — bloink.',
                  u'Bla \\@-- blub \\@--- bloink.'],
                 [u'Bla „deutsch“ “american” ”unusual“.',
                  u'Bla \\@"`deutsch\\@"\' \\@"`american\\@"\' \\@"`unusual\\@"\'.'],
                 [u'Bla «französisch» oder « französisch ».',
                  u'Bla \\@"`französisch\\@"\' oder \\@\\@"` französisch \\@\\@"`.'],
                 [u'Bla „(deutsch,“ “(american,” ”(unusual,“.',
                  u'Bla \\@"`(deutsch,\\@"\' \\@"`(american,\\@"\' \\@"`(unusual,\\@"\'.'],
                 [u'„$einsam$ $lonely$” $quote$“ here.',
                  u'\\@"`$einsam$ $lonely$\\@"\' $quote$\\@"\' here.'],
                 [u'Bla »blub« bloink.',
                  u'Bla \\@"`blub\\@"\' bloink.'],
                 [u'\'Bla\' ‚blub‘ ‚bloink’ ›blub‹ ‹bloink›.',
                  u'\\@\'Bla\\@\' \\@\'blub\\@\' \\@\'bloink\\@\' \\@\'blub\\@\' \\@\'bloink\\@\'.'],
                 [u'„‚Nested quotes‘”.',
                  u'\\@\\@"`\\@\'Nested quotes\\@\'\\@\\@"`.'] ]

    pageReferences = [ [u'Auf S. 4 Abs. 3 in Art. 7 steht',
                        u'Auf \\@S.\\,4 \\@Abs.\\,3 in \\@Art.\\,7 steht'],
                       [u'Auf Seite 4 Absatz 3 in Artikel 7 steht',
                        u'Auf Seite~4 Absatz~3 in Artikel~7 steht'],
                       [u'Auf S.4-6 steht',
                        u'Auf \\@S.\\,4\\@--6 steht'],
                       [u'Auf S.4--6 steht',
                        u'Auf \\@S.\\,4--6 steht'],
                       [u'Auf S. 4f steht',
                        u'Auf \\@S.\\,4\\,f. steht'],
                       [u'S. 4 ff. besagt',
                        u'\\@S.\\,4\\,ff. besagt'],
                       [u'Es fehlen Angaben zu S. Abs. Art.',
                        u'Es fehlen Angaben zu \\@S. \\@Abs. \\@Art.'] ]

    spacing = [ [u'A number range 6--9 is nice.',
                 u'A number range 6--9 is nice.'],
                [u'6 -- 9 is as nice as 6-- 9, 6 --9 and 6 - 9 or 6- 9.',
                 u'6\\@--9 is as nice as 6\\@--9, 6\\@--9 and 6\\@--9 or 6\\@--9.'],
                [u'Now we do - with all due respect --, an intersperse.',
                 u'Now we do \\@-- with all due respect \\@--, an intersperse.'],
                [u'Followed by an afterthougt -- here it comes.',
                 u'Followed by an afterthougt \\@-- here it comes.'],
                [u'Followed by an afterthougt---here it comes.',
                 u'Followed by an afterthougt\\@---here it comes.'],
                [u'Here come some dots ...',
                 u'Here come some dots~\\@\\dots{}'],
                [u'Here come some dots...',
                 u'Here come some dots\\@\\dots{}'],
                [u'Dots in math $a_1,...,a_n$ should work without spacing.',
                 u'Dots in math $a_1,\\@\\dots{},a_n$ should work without spacing.'],
                [u'And dots ... in … the middle.',
                 u'And dots~\\@\\dots{} in~\\@\\dots{} the middle.'],
                [u'And dots...in the middle.',
                 u'And dots\\@\\dots{}in the middle.'],
                [u'And dots [...] for missing text.',
                 u'And dots [\\@\\dots{}\\kern-.16em] for missing text.'] ]

    lawReference = [ [u'In §§1ff. HGB steht',
                      u'In §§\\,1\\,ff. \\@\\acronym{HGB} steht'],
                     [u'In § 1 f. HGB steht',
                      u'In §\\,1\\,f. \\@\\acronym{HGB} steht'],
                     [u'In § 1 Abs. 1 HGB steht',
                      u'In §\\,1 \\@Abs.\\,1 \\@\\acronym{HGB} steht'],
                     [u'In § 1 Absatz 1 Satz 2 HGB steht',
                      u'In §\\,1 Absatz~1 Satz~2 \\@\\acronym{HGB} steht'],
                     [u'In §§ 10-15 HGB steht',
                      u'In §§\\,10\\@--15 \\@\\acronym{HGB} steht'],
                     [u'Ein verlorener § und noch ein §',
                      u'Ein verlorener \\@§ und noch ein \\@§'] ]

    numbers = [ [u'We have 10000, 2000 and 3000000 and -40000 and -5000.',
                 u'We have 10\\,000, 2000 and 3\\,000\\,000 and \\@$-$40\\,000 and \\@$-$5000.'],
                [u'We are in the 21. regiment and again in the 21.regiment.',
                 u'We are in the \\@21. regiment and again in the \\@21.regiment.'],
                [u'bis zu 30 000 Einwohner',
                 u'bis zu 30 000 Einwohner'],
                [u'Kennwort 0000 ist unsicher, 00000 auch, 0000000 nicht weniger',
                 u'Kennwort 0000 ist unsicher, 00\,000 auch, 0\,000\,000 nicht weniger'],
                [u'some 5,000 races',
                 u'some 5,000 races'],
                [u'pi ist 3,14159',
                 u'pi ist 3,14\,159'],  # this is not really what we want, but too rare and too complex to find an automatic solution
                [u'bla 2004-2006 blub',
                 u'bla 2004\@--2006 blub']
              ]

    dates = [ [u'The date is 19.5.2012 or 19. 10. 95 for good.',
               u'The date is \\@19.\\,5.\\,2012 or \\@19.\\,10.\\,95 for good.'] ]

    units = [ [u'Units: 21kg, 4MW, 1mV, 13-14TeV, 5°C.',
               u'Units: 21\\,kg, 4\\,MW, 1\\,\\@mV, 13\\@--14\\,\\@TeV, 5\\,°C.'],
              [u'Decimal number with unit or unicode prefix: 25,4mm and 1.2μm.',
               u'Decimal number with unit or unicode prefix: 25,4\\,mm and 1.2\\,μm.'],
              [u'Units: 21 kg, 4 MW, 1 mV , 13--14 TeV, 5 °C.',
               u'Units: 21\\,kg, 4\\,MW, 1\\,\\@mV , 13--14\\,\\@TeV, 5\\,°C.'],
              [u'Decimal number with unit: 25,4 mm.',
               u'Decimal number with unit: 25,4\\,mm.'],
              [u'Percentages like 5 % should be handled as nicely as 5%.',
               u'Percentages like 5\\@\\,\\% should be handled as nicely as 5\\,\\%.'],
              [u'90° is a right angle.',
               u'90° is a right angle.'] ]

    code = [ [u'|increase(i)| increases |i|, by one.',
              u'\\@\\lstinline|increase(i)| increases \\@\\lstinline|i|, by one.'] ]

    urls = [ [u'http://www.google.de',
              u'\\@\\url{http://www.google.de}'],
             [u'(siehe http://www.google.de)',
              u'(siehe \\@\\url{http://www.google.de})'],
             [u'http://www.google.de bla',
              u'\\@\\url{http://www.google.de} bla'],
             [u'http://www.google.de www.bla.de',
              u'\\@\\url{http://www.google.de} \\@\\url{www.bla.de}'],
             [u'http://www.google.de\nwww.bla.de',
              u'\\@\\url{http://www.google.de} \\@\\url{www.bla.de}'],
             [u'https://duckduckgo.com/?q=find&ia=web',
              u'\\@\\url{https://duckduckgo.com/?q=find&ia=web}'],
             [u'https://www.bla.com. Sowie http://www.blub.org?',
              u'\\@\\url{https://www.bla.com}. Sowie \\@\\url{http://www.blub.org}?'],
             [u'https://commons.wikimedia.org/wiki/File:Barf%C3%BCsserArkade1.jpg', # note that % needs to be escaped (else starts comment)
              u'\\@\\url{https://commons.wikimedia.org/wiki/File:Barf\%C3\%BCsserArkade1.jpg}'],
             [u'https://commons.wikimedia.org/wiki/File:Barfuesser_Arkade1.jpg',
              u'\\@\\url{https://commons.wikimedia.org/wiki/File:Barfuesser_Arkade1.jpg}'],
             [u'auf www.bla.com lesen',
              u'auf \\@\\url{www.bla.com} lesen'],
             [u'siehe www.bla.com.',
              u'siehe \\@\\url{www.bla.com}.'],
             [u'Das www.ist_keine_hervorhebung.de!',
              u'Das \\@\\url{www.ist_keine_hervorhebung.de}!'],
             [u'http://www.bla.com/foo}\\evilCommand',
              u'\\@\\url{http://www.bla.com/foo}\\@\}\\@\\forbidden\\evilCommand']
             ]

    sectionsAndAuthors = [ [u'[foo]\n(bar)',
                            u'\\section{foo}\n\\authors{bar}'],
                           [u'[[foo]]\n\n(bar)',
                            u'\\subsection{foo}\n\n(bar)'] ]

    sectionsWithEmph = [ [u'[Ola Gjeilo: _Northern Lights_]',
                          u'\\section{Ola Gjeilo: \\emph{Northern Lights}}'],
                         [u'[_Mein BAMF_ -- aus dem Kabarett]',
                          u'\\section{\\emph{Mein \\@\\acronym{BAMF}} \\@-- aus dem Kabarett}'],
                         [u'[Max Reger: _Es waren zwei Königskinder_ hier]',
                          u'\\section{Max Reger: \\emph{Es waren zwei Königskinder} hier}'],
                         [u'[[Ola Gjeilo: _Northern Lights_]]',
                          u'\\subsection{Ola Gjeilo: \\emph{Northern Lights}}'],
                         [u'[[_Mein BAMF_ -- aus dem Kabarett]]',
                          u'\\subsection{\\emph{Mein \\@\\acronym{BAMF}} \\@-- aus dem Kabarett}'],
                         [u'[[Max Reger: _Es waren zwei Königskinder_ hier]]',
                          u'\\subsection{Max Reger: \\emph{Es waren zwei Königskinder} hier}'],
                         [u'[1. Buch Mose]',
                          u'\\section{\\@1. Buch Mose}'] ]

    numericalScope = [ [u'10\xb3 Meter sind ein km',
                        u'10\xb3 Meter sind ein km'] ]

    codeAndLengthyParagraph = [ [u'Larem ipsum dolor sit amet |rhoncus| lerem ipsum dolor sit amet\nlirem ipsum dolor sit amet lorem ipsum dolor sit amet\nlurem ipsum dolor sit amet.\n\nUnd hier ist noch ein Absatz. Lorem ipsum dolor sit amet. Und so weiter.',
                                 u'Larem ipsum dolor sit amet \\@\\lstinline|rhoncus| lerem ipsum dolor sit\namet lirem ipsum dolor sit amet lorem ipsum dolor sit amet lurem ipsum\ndolor sit amet.\n\nUnd hier ist noch ein Absatz. Lorem ipsum dolor sit amet. Und so\nweiter.'] ]

    ednoteEscape = [ [u"""before

{{

Bobby Tables...

\\end{ednote}

\\herebedragons

}}

after""",
u"""before

\\begin{ednote}

Bobby Tables...

\\@|end{ednote}

\\herebedragons

\\end{ednote}

after""" ] ]

    multilineCaptions = [ [u'Dies ist eine Bildunterschrift.\n\nSie soll zwei Absätze haben.',
                           u'Dies ist eine Bildunterschrift.\\@\\@\\@\nSie soll zwei Absätze haben.' ] ]

class ExporterTestCases:
    """
    Which tests should be run for the separate parsers?
    """
    testsEverywhere = [ ExporterTestStrings.quotes,
                        ExporterTestStrings.abbreviation,
                        ExporterTestStrings.acronym,
                        ExporterTestStrings.escaping,
                        ExporterTestStrings.mathEnvironments,
                        ExporterTestStrings.evilUTF8,
                        ExporterTestStrings.pageReferences,
                        ExporterTestStrings.spacing,
                        ExporterTestStrings.lawReference,
                        ExporterTestStrings.numbers,
                        ExporterTestStrings.dates,
                        ExporterTestStrings.units,
                        ExporterTestStrings.urls,
                        ExporterTestStrings.numericalScope ]

    # Text vs. Titles
    testsInText = testsEverywhere + \
                  [ ExporterTestStrings.itemizeAndCo,
                    ExporterTestStrings.code,
                    ExporterTestStrings.ednoteEscape,
                    ExporterTestStrings.codeAndLengthyParagraph  ]

    lineGroupTests = testsInText + \
                     [ ExporterTestStrings.sectionsAndAuthors,
                       ExporterTestStrings.sectionsWithEmph ]

    titleTests = testsEverywhere

    captionTests = [[[i, j.replace(u'\n\n', u'\\@\\@\\@\n')] for i, j in k] for k in testsInText] + \
                   [ ExporterTestStrings.multilineCaptions ]

class DokuforgeParserUnitTests(DfTestCase):
    def verifyReturnTypes(self, text):
        pseq = dfLineGroupParser(text)
        assert isinstance(pseq.debug(), tuple)
        assert isinstance(pseq.toTex(), unicode)
        assert isinstance(pseq.toHtml(), unicode)
        assert isinstance(pseq.toDF(), unicode)
        assert isinstance(pseq.toEstimate(), Estimate)

    def testLineGroupParser(self):
        [ [self.verifyReturnTypes(s[0]) for s in t] for t in ExporterTestCases.lineGroupTests ]

class DokuforgeMicrotypeUnitTests(DfTestCase):
    def verifyExportsTo(self, df, tex):
        obtained = dfLineGroupParser(df).toTex().strip()
        self.assertEqual(obtained, tex)

    def testLineGroupParser(self):
        [ [self.verifyExportsTo(s[0],s[1]) for s in t] for t in ExporterTestCases.lineGroupTests ]


class DokuforgeTitleParserTests(DfTestCase):
    def verifyExportsTo(self, df, tex):
        obtained = dfTitleParser(df).toTex().strip()
        self.assertEqual(obtained, tex)

    def testTitleParser(self):
        [ [self.verifyExportsTo(s[0],s[1]) for s in t] for t in ExporterTestCases.titleTests ]

class DokuforgeCaptionParserTests(DfTestCase):
    def verifyExportsTo(self, df, tex):
        obtained = dfCaptionParser(df).toTex().strip()
        self.assertEqual(obtained, tex)

    def testCaptionParser(self):
        [ [self.verifyExportsTo(s[0],s[1]) for s in t] for t in ExporterTestCases.captionTests ]

if __name__ == '__main__':
    unittest.main()
