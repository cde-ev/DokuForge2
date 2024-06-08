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
import subprocess

import createexample
from dokuforge import buildapp
from dokuforge.paths import PathConfig
from dokuforge.parser import dfLineGroupParser, dfTitleParser, dfCaptionParser, Estimate, allowedMathSymbolCommands
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

try:
    unicode
except NameError:
    unicode = str


teststrings = [
    ("simple string", "simple string"),
    ("some chars <>/& here", "some chars &lt;&gt;/&amp; here"),
    ("exotic äöüß 囲碁 chars", "exotic äöüß 囲碁 chars"),
    ("some ' " + '" quotes', "some &#39; &#34; quotes")
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
        self.assertIn(b"\0\0\0\0\0\0\0\0\0\0", octets)

    def assertIsTarGz(self, octets):
        f = gzip.GzipFile('dummyfilename', 'rb', 9, io.BytesIO(octets))
        self.assertIsTar(f.read())

    def assertLooksLikeRcs(self, octets):
        # FIXME: find a better check for whether something looks like an rcs file
        self.assertTrue(octets.startswith(b"head"))

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
        self.tmpdir = tempfile.mkdtemp(prefix="dokuforge").encode("ascii")
        self.storage = CachingStorage(self.tmpdir, b"db")
        self.userdb = UserDB(self.storage)
        os.makedirs(os.path.join(self.tmpdir, b'aca123/course42'))
        os.makedirs(os.path.join(self.tmpdir, b'aca123/course4711'))
        self.academy = Academy(os.path.join(self.tmpdir, b'aca123'),
                               lambda : ['abc', 'cde'])
        self.academy.setgroups(['cde'])

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
        user = self.getUser("userfoo")
        self.assertTrue(user.allowedRead(self.academy))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse('course42')))
        self.assertFalse(user.allowedRead(self.academy, self.academy.getCourse('course4711')))

    def testReadRecursive(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_read_aca123 True
""")
        user = self.getUser("userfoo")
        self.assertTrue(user.allowedRead(self.academy))
        self.assertTrue(user.allowedRead(self.academy, recursive=True))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse('course42')))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse('course4711')))

    def testReadNonRecursive(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_view_aca123 True
""")
        user = self.getUser("userfoo")
        self.assertFalse(user.allowedRead(self.academy, recursive=True))

    def testReadRevoke(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_read_aca123 True,kurs_read_aca123_course42 False
""")
        user = self.getUser("userfoo")
        self.assertTrue(user.allowedRead(self.academy))
        self.assertFalse(user.allowedRead(self.academy, self.academy.getCourse('course42')))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse('course4711')))

    def testWriteSimple(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = kurs_write_aca123_course42 True
""")
        user = self.getUser("userfoo")
        self.assertFalse(user.allowedWrite(self.academy))
        self.assertTrue(user.allowedWrite(self.academy, self.academy.getCourse('course42')))
        self.assertFalse(user.allowedWrite(self.academy, self.academy.getCourse('course4711')))

    def testWriteRevoke(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_write_aca123 True,kurs_write_aca123_course42 False
""")
        user = self.getUser("userfoo")
        self.assertTrue(user.allowedWrite(self.academy))
        self.assertFalse(user.allowedWrite(self.academy, self.academy.getCourse('course42')))
        self.assertTrue(user.allowedWrite(self.academy, self.academy.getCourse('course4711')))

    def testAdminNonrevokable(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = df_superadmin True,kurs_read_aca123_course42 False,kurs_write_aca123_course4711 False
""")
        user = self.getUser("userfoo")
        self.assertTrue(user.allowedRead(self.academy))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse('course42')))
        self.assertTrue(user.allowedRead(self.academy, self.academy.getCourse('course4711')))
        self.assertTrue(user.allowedWrite(self.academy, self.academy.getCourse('course42')))
        self.assertTrue(user.allowedWrite(self.academy, self.academy.getCourse('course4711')))

    def testMetaSimple(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = akademie_meta_aca123 True
""")
        user = self.getUser("userfoo")
        self.assertTrue(user.allowedMeta(self.academy))

    def testMetaGroup(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = gruppe_meta_cde True
""")
        user = self.getUser("userfoo")
        self.assertTrue(user.allowedMeta(self.academy))

    def testMetaRevoke(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = gruppe_meta_cde True,akademie_meta_aca123 False
""")
        user = self.getUser("userfoo")
        self.assertFalse(user.allowedMeta(self.academy))

    def testGlobalNonRevoke(self):
        self.writeUserDbFile(b"""
[userfoo]
status = cde_dokubeauftragter
password = abc
permissions = df_meta True,akademie_meta_aca123 False
""")
        user = self.getUser("userfoo")
        self.assertTrue(user.allowedMeta(self.academy))

class DokuforgeWebTests(DfTestCase):
    url = "http://www.dokuforge.de"
    size = None  # will be set in derived classes

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="dokuforge").encode("ascii")
        self.pathconfig = PathConfig()
        self.pathconfig.rootdir = self.tmpdir
        createexample.main(size=self.size, pc=self.pathconfig)
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

class DokuforgeBigWebTests(DokuforgeWebTests):
    """Tests requiring a big dokuforge example instance"""

    size = 100

    def testCourseLessPrivileged(self):
        self.do_login(username="arthur", password="mypass")
        self.res = self.res.click(description="Beste Akademie ever")
        self.res.mustcontain("Helenistische Heldenideale")
        self.res = self.res.click(href="course01/$")
        self.res.mustcontain("Example Section")
        self.is_loggedin()

class DokuforgeSmallWebTests(DokuforgeWebTests):
    """Tests of dokuforge functionality (excluding exporting) for which a
    small instance is sufficient"""

    size = 1

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
        self.is_loggedin()

    def testLogout(self):
        self.do_login()
        self.do_logout()
        self.res.mustcontain(no="/logout")

    def testAcademy(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.is_loggedin()
        self.res.mustcontain("Export")

    def testCourse(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.is_loggedin()
        self.res.mustcontain("df2-Rohdaten")

    def testPage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
        self.is_loggedin()
        self.res.mustcontain("neues Bild hinzuf")

    def testEdit(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
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
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
        self.res = self.res.click(description="Editieren", index=1)
        form = self.res.forms[1]
        form["content"] = \
r"""[Section]
(Authors)
*keyword*, $\sqrt{2}$ and _emphasis_
$$\sqrt{2}$$
[[subsection]]
- bullet1
- bullet2 https://www.someurl.org
chars like < > & " to be escaped and an { ednote \end{ednote} }
"""
        self.res = form.submit(name="saveshow")
        expected_linked_url = '<a href="https://www.someurl.org" rel="noopener">https://www.someurl.org</a>'
        self.res.mustcontain(r"$\sqrt{2}$", r"ednote \end{ednote}", expected_linked_url)
        self.is_loggedin()

    def testTitleWithEmph(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
        self.res = self.res.click(description="Editieren", index=1)
        form = self.res.forms[1]
        form["content"] = "[ _A_ ]"  # single line
        self.res = form.submit(name="saveshow")
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.is_loggedin()

    def testMovePage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        form = self.res.forms[1]
        self.res = form.submit()
        self.is_loggedin()

    def testCreatePage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        form = self.res.forms[2]
        self.res = form.submit()
        self.is_loggedin()
        self.res.mustcontain("Teil&nbsp;#2")

    def testCourseTitle(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="/.*title$")
        for (inputstr, outputstr) in teststrings:
            form = self.res.forms[1]
            form["content"] = inputstr
            self.res = form.submit(name="saveedit")
            self.res.mustcontain(outputstr)
        self.is_loggedin()

    def testDeletePage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
        form = self.res.forms[1]
        self.res = form.submit()
        self.res.mustcontain(no="Teil&nbsp;#0")
        self.is_loggedin()

    def testRestorePage(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
        form = self.res.forms[1]
        self.res = form.submit()
        self.res = self.res.click(href="course01/.*deadpages$")
        form = self.res.forms[1]
        self.res = form.submit()
        self.res.mustcontain("Teil&nbsp;#0")
        self.is_loggedin()

    def testAcademyTitle(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="/.*title$")
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
        self.res = self.res.click(href="/.*createcourse$")
        form = self.res.forms[1]
        form["name"] = "course03"
        form["title"] = "Testkurs"
        self.res = form.submit()
        self.res.mustcontain("Area51", "Testkurs")
        self.res = self.res.click(href="/.*createcourse$")
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
        self.res = self.res.click(href="course01/$")
        form = self.res.forms[3]
        self.res = form.submit()
        self.res.mustcontain(no="Area51")
        self.res = self.res.click(href="deadcourses$")
        form = self.res.forms[1]
        self.res = form.submit()
        self.res.mustcontain("Area51")

    def testCreateAcademy(self):
        self.do_login()
        self.res = self.res.click(href="/createacademy$")
        form = self.res.forms[1]
        form["name"] = "newacademy-2001"
        form["title"] = "Testakademie"
        form["groups"] = ["cde"]
        self.res = form.submit()
        self.res.mustcontain("Testakademie", "X-Akademie")
        self.res = self.res.click(href="/createacademy$")
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

    @staticmethod
    def _normalizeToTextareaLineEndings(form_contents: str) -> str:
        # when editing in the browser, textareas encode line endings as \r\n, mimic this in the tests
        normalized_to_newline = form_contents.replace('\r\n', '\n').replace('\n\r', '\n').replace('\r', '\n')
        return normalized_to_newline.replace('\n', '\r\n')

    def testGroups(self):
        valid_groups_input = """[cde]
title = CdE-Akademien

[spam]
title = Wie der Name sagt
"""

        invalid_groups_input = """[cde]
title = CdE-Akademien

[spam
title = Wie der Name sagt
"""

        def testValidInput():
            form = self.res.forms[1]
            form["content"] = self._normalizeToTextareaLineEndings(valid_groups_input)
            self.res = form.submit(name="saveedit")
            self.res.mustcontain("&Auml;nderungen erfolgreich gespeichert.")

        def testInvalidInput():
            form = self.res.forms[1]
            form["content"] = self._normalizeToTextareaLineEndings(invalid_groups_input)
            self.res = form.submit(name="saveedit")
            self.res.mustcontain("Es ist ein allgemeiner Parser-Fehler aufgetreten!")

        def testInvalidCharacters():
            form = self.res.forms[1]
            form["content"] = self._normalizeToTextareaLineEndings("""[cde]
title = CdE-Akademien

[spam]
title = a^b!c"d§e$f%g&h/i(j)k=l?m´n+o*p~q#r's<t>u|v,w;x.y:z-a_b°c{d[e]f}gµh²i•j𐂂k l${bla:blub}m
""")
            self.res = form.submit(name="saveedit")
            self.res.mustcontain("Ungültige Zeichen enthalten!")


        def testCancelEdit():
            form = self.res.forms[1]
            form["content"] = self._normalizeToTextareaLineEndings(invalid_groups_input)
            self.res = self.res.click(description="Zurücksetzen", index=0)
            self.res.mustcontain(valid_groups_input)

        def testRcsAvailability():
            self.res = self.res.click(description="rcs", index=0)
            self.assertLooksLikeRcs(self.res.body)

        self.do_login()
        self.res = self.res.click(href="/groups/$")
        testValidInput()
        testInvalidInput()
        testInvalidCharacters()
        testCancelEdit()
        self.is_loggedin()
        testRcsAvailability()

    @staticmethod
    def _getFormContentsWithPassword(password: str) -> str:
        return """[bob]
name = bob
status = überadmin
password = """ + password + """
permissions = df_superadmin True,df_admin True"""

    def testAdmin(self):
        invalid_syntax_input = """[bob
name = bob
status = ueberadmin
password = secret
permissions = df_superadmin True,df_admin True
"""

        duplicate_user_input = """[bob]
name = bob
status = überadmin
password = secret
permissions = df_superadmin True,df_admin True

[bob]
name = otherbob
status = überadmin
password = geheim
permissions = df_superadmin True,df_admin True"""

        def testValidInput():
            form = self.res.forms[1]
            form["content"] = self._getFormContentsWithPassword("new_secret")
            self.res = form.submit(name="saveedit")
            self.res.mustcontain("&Auml;nderungen erfolgreich gespeichert.")

        def testInvalidSyntax():
            form = self.res.forms[1]
            form["content"] = self._normalizeToTextareaLineEndings(invalid_syntax_input)
            self.res = form.submit(name="saveedit")
            self.res.mustcontain("Es ist ein allgemeiner Parser-Fehler aufgetreten!")

        def testCancelEdit():
            form = self.res.forms[1]
            form["content"] = self._normalizeToTextareaLineEndings(invalid_syntax_input)
            self.res = self.res.click(description="Zurücksetzen", index=0)
            self.res.mustcontain(self._getFormContentsWithPassword("new_secret"))

        def testMissingFields():
            form = self.res.forms[1]
            form_contents = ["[bob]", "name = bob", "status = ueberadmin", "password = secret", "permissions = df_superadmin True,df_admin True"]
            for incomplete_indices in ((0, 1, 3, 4), (0, 1, 2, 4)):
                form["content"] = self._normalizeToTextareaLineEndings("\n".join([form_contents[i] for i in incomplete_indices]))
                self.res = form.submit(name="saveedit")
                self.res.mustcontain("Es fehlt eine Angabe!")

        def testMalformedPermissions():
            form = self.res.forms[1]
            some_form_contents = ["[bob]", "name = bob", "status = ueberadmin", "password = secret"]
            for malformed_permission in ("df superadmin True", "df_admin"):
                form["content"] = self._normalizeToTextareaLineEndings("\n".join(some_form_contents) + '\npermissions = ' + malformed_permission)
                self.res = form.submit(name="saveedit")
                self.res.mustcontain("Das Recht")
                self.res.mustcontain("ist nicht wohlgeformt.")

        def testDuplicateUserWarning():
            form = self.res.forms[1]
            form["content"] = self._normalizeToTextareaLineEndings(duplicate_user_input)
            self.res = form.submit(name="saveedit")
            self.res.mustcontain("Doppelter Nutzername")

        self.do_login()
        self.res = self.res.click(href="/admin/$")

        testValidInput()
        testInvalidSyntax()
        testCancelEdit()
        testMissingFields()
        testMalformedPermissions()
        testDuplicateUserWarning()

        self.is_loggedin()

    def testAdminComplicatedPassword(self):
        def _trySettingComplicatedPassword():
            self.res = self.res.click(href="/admin/$")
            form = self.res.forms[1]
            complicated_password = """a^b!c"d§e$f%g&h/i(j)k=l?m´n+o*p~q#r's<t>u|v,w;x.y:z-a_b°c{d[e]f}gµh²i•j𐂂k l${bla:blub}m"""
            form["content"] = self._normalizeToTextareaLineEndings(self._getFormContentsWithPassword(complicated_password))
            self.res = form.submit(name="saveedit")
            self.res.mustcontain("Ungültige Zeichen enthalten!")

        # implemented as a separate test case to avoid interference with other admin test cases due to logging out and in
        self.do_login()
        _trySettingComplicatedPassword()
        self.res = self.res.forms[0].submit("submit")     # cannot use do_logout because we have multiple forms
        self.res.mustcontain(no="/logout")                # verify that we are logged out
        self.do_login(username="bob", password="secret")  # verify that we can still log in with the previous password
        self.is_loggedin()
        _trySettingComplicatedPassword()
        form = self.res.forms[1]
        form["content"] =self._normalizeToTextareaLineEndings(self._getFormContentsWithPassword("secret"))
        self.res = form.submit(name="saveedit")           # verify that we can save after removing illegal characters
        self.res.mustcontain("&Auml;nderungen erfolgreich gespeichert.")

    def testAdminRcs(self):
        self.do_login()
        self.res = self.res.click(href="/admin/$")
        self.res = self.res.click(description="rcs", index=0)
        self.assertLooksLikeRcs(self.res.body)

    def testStyleguide(self):
        self.res = self.app.get("/")
        self.res = self.res.click(href="/style/$")
        self.res.mustcontain("Hier erfährst du, was bei der Eingabe der Texte in DokuForge")
        self.res = self.res.click(href="/style/grundlagen$")
        self.res.mustcontain("Bedienung von DokuForge")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/abbildungen$")
        self.res.mustcontain("Abbildungen")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/mathe$")
        self.res.mustcontain("Mathematik-Umgebung")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/gedichte$")
        self.res.mustcontain("Gedichte")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/literatur$")
        self.res.mustcontain("Literatur")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/tabellen$")
        self.res.mustcontain("Tabellen")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/konflikte$")
        self.res.mustcontain("Konflikte")
        self.res = self.res.click(description="Login")
        self.do_login()
        self.res = self.res.click(href="/style/$", index=0)
        self.res.mustcontain("Hier erfährst du, was bei der Eingabe der Texte in DokuForge")
        self.res = self.res.click(href="/style/grundlagen$")
        self.res.mustcontain("Bedienung von DokuForge")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/abbildungen$")
        self.res.mustcontain("Abbildungen")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/mathe$")
        self.res.mustcontain("Mathematik-Umgebung")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/gedichte$")
        self.res.mustcontain("Gedichte")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/literatur$")
        self.res.mustcontain("Literatur")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/tabellen$")
        self.res.mustcontain("Tabellen")
        self.res = self.res.click(href="/style/$", index=0)
        self.res = self.res.click(href="/style/konflikte$")
        self.res.mustcontain("Konflikte")
        self.is_loggedin()

    def _uploadExampleBlob(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
        self.res = self.res.click(href="course01/0/.*addblob$")
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = "blob"
        self.res = form.submit()
        form = self.res.forms[1]
        form["content"] = Upload("README-rlog.txt")
        self.res = form.submit()

    def testAddBlob(self):
        self._uploadExampleBlob()
        self.res.mustcontain("Zugeordnete Bilder", "#[0] (README-rlog.txt)")
        self.is_loggedin()

    def testShowBlob(self):
        self._uploadExampleBlob()
        self.res = self.res.click(href="course01/0/0/$")
        self.res.mustcontain("Bildunterschrift/Kommentar: Shiny blob",
                             "K&uuml;rzel: blob")
        self.is_loggedin()

    def testMD5Blob(self):
        self._uploadExampleBlob()
        self.res = self.res.click(href="course01/0/0/$")
        self.res = self.res.click(href="course01/0/0/.*md5$")
        self.res.mustcontain("MD5 Summe des Bildes ist")
        self.is_loggedin()

    def testDownloadBlob(self):
        self._uploadExampleBlob()
        self.res = self.res.click(href="course01/0/0/$")
        self.res = self.res.click(href="course01/0/0/.*download$")
        self.res.mustcontain("======")

    def testEditBlob(self):
        self._uploadExampleBlob()
        self.res = self.res.click(href="course01/0/0/$")
        self.res = self.res.click(href="course01/0/0/.*edit$")
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
        self._uploadExampleBlob()
        self.res.mustcontain("Zugeordnete Bilder", "#[0] (README-rlog.txt)")
        form = self.res.forms[3]
        self.res = form.submit()
        self.res.mustcontain("Keine Bilder zu diesem Teil gefunden.",
                             no="#[0] (README-rlog.txt)")
        self.is_loggedin()

    def testRestoreBlob(self):
        self._uploadExampleBlob()
        form = self.res.forms[3]
        self.res = form.submit()
        self.res.mustcontain("Keine Bilder zu diesem Teil gefunden.",
                             no="#[0] (README-rlog.txt)")
        self.res = self.res.click(href="course01/0/.*deadblobs$")
        self.res.mustcontain("#[0] (README-rlog.txt)")
        form = self.res.forms[1]
        self.res = form.submit()
        self.res.mustcontain("Zugeordnete Bilder", "#[0] (README-rlog.txt)")
        self.is_loggedin()

    def testAddBlobEmptyLabel(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
        self.res = self.res.click(href="course01/0/.*addblob$")
        form = self.res.forms[1]
        form["comment"] = "Shiny blob"
        form["label"] = ""
        self.res = form.submit()
        form = self.res.forms[1]
        self.res.mustcontain("Kürzel nicht wohlgeformt!")
        self.is_loggedin()

    def testPartDeletion(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res.mustcontain("Area51")
        self.res = self.res.click(href="/.*createcourse$")
        form = self.res.forms[1]
        form["name"] = "bug"
        form["title"] = "bug"
        self.res = form.submit()
        self.res.mustcontain("Area51", "bug")
        self.res = self.res.click(href="/bug/$")
        self.res = self.res.forms[1].submit() # create new part
        self.res = self.res.click(href="/bug/0/$", index=0)
        self.res = self.res.forms[1].submit() # delete only part

class DokuforgeExporterTests(DokuforgeWebTests):
    """Check whether exporting data from within dokuforge works.

    This requires a small dokuforge example instance, hence inherits from
    DokuforgeWebTests.
    Microtypography (exporting of strings) is tested in ExporterTestCases.
    """

    size = 1

    def testRawCourseExport(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course02/$")
        self.res = self.res.click(description="df2-Rohdaten")
        self.assertIsTarGz(self.res.body)

    def testRawPageExport(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(href="course01/$")
        self.res = self.res.click(href="course01/0/$", index=0)
        self.res = self.res.click(description="rcs", index=0)
        self.assertLooksLikeRcs(self.res.body)

    def testRawAcademyExport(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(description="df2-Rohdaten")
        self.assertIsTarGz(self.res.body)

    def testAcademyExport(self):
        self.do_login()
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(description="Export")
        self.assertIsTarGz(self.res.body)

    def _getExportAsTar(self):
        self.res = self.res.click(description="X-Akademie")
        self.res = self.res.click(description="Export")
        tarFile = tarfile.open(mode='r', fileobj=io.BytesIO(self.res.body))
        return tarFile

    def testExpectedFilesExist(self):
        self.do_login()
        tarFile = self._getExportAsTar()
        expectedMembers = ['texexport_xa2011-1/WARNING',
                           'texexport_xa2011-1/course01/chap.tex',
                           'texexport_xa2011-1/course02/chap.tex',
                           'texexport_xa2011-1/contents.tex']
        memberNames = tarFile.getnames()
        for filename in expectedMembers:
            self.assertIn(filename, memberNames)

    def testExpectedInfrastructureFileContents(self):
        self.do_login()
        tarFile = self._getExportAsTar()
        warningText = tarFile.extractfile("texexport_xa2011-1/WARNING").read().decode()
        self.assertGreater(len(warningText), 50)
        contentsText = tarFile.extractfile("texexport_xa2011-1/contents.tex").read().decode()
        self.assertIn(r"\input{course01/chap}", contentsText)
        self.assertIn(r"\input{course02/chap}", contentsText)

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

        imageFilenames = imageFilenamesUnchanged + list(imageFilenamesToBeChanged.keys())

        def _addImagesToCourse01():
            os.chdir('testData')
            counter = 0  # to achieve distinct labels
            for imageFilename in imageFilenames:
                self.res = self.res.click(description="X-Akademie")
                self.res = self.res.click(href="course01/$")
                self.res = self.res.click(href="course01/0/$", index=0)
                self.res = self.res.click(href="course01/0/.*addblob$")
                form = self.res.forms[1]
                form["comment"] = "Kommentar"
                form["label"] = "blob" + str(counter)
                self.res = form.submit()
                form = self.res.forms[1]
                form["content"] = Upload(imageFilename)
                self.res = form.submit()
                counter = counter + 1
            os.chdir('..')

        def _checkExportedFilenames(tarFile):
            expectedFilenamesInExport = imageFilenamesUnchanged + list(imageFilenamesToBeChanged.values())
            memberNames = tarFile.getnames()

            filenamesInExport = []
            for m in memberNames:
                filenamesInExport.append(m.split('/')[-1])

            # check if all expected file names are present
            # note that they are prefixed by blob_#_ when exporting
            for expectedFilename in expectedFilenamesInExport:
                found = False
                for f in filenamesInExport:
                    if f.endswith(expectedFilename):
                        found = True
                self.assertTrue(found)

        def _checkFilenamesInComment(exportedCourseTexWithImages):
            filenamesExpectedInComment = imageFilenamesToBeChanged.keys()
            for filename in filenamesExpectedInComment:
                expectedLine = "%% Original-Dateiname: %s" % (filename,)
                self.assertIn(expectedLine, exportedCourseTexWithImages)

        def _checkFilenamesInIncludegraphics(exportedCourseTexWithImages):
            filenamesExpectedInIncludegraphics = imageFilenamesToBeChanged.values()
            for filename in filenamesExpectedInIncludegraphics:
                expectedLineRegex = r"\\includegraphics\[height=12\\baselineskip\]\{course01/blob_\d+_%s\}" \
                                    % (filename,)
                self.assertNotEqual(re.findall(expectedLineRegex, exportedCourseTexWithImages), [])

        def _checkFilenamesExpectedNotIncluded(exportedCourseTexWithImages):
            filenamesExpectedNotIncluded = {i for i in imageFilenamesUnchanged
                                            if (not i.endswith('.jpg') and
                                                not i.endswith('.png') and
                                                not i.endswith('.pdf'))}
            for filename in filenamesExpectedNotIncluded:
                expectedLineRegex = r"%%\\includegraphics\[height=12\\baselineskip\]\{course01/blob_\d+_%s\}" \
                                    % (filename,)
                self.assertNotEqual(re.findall(expectedLineRegex, exportedCourseTexWithImages), [])
                expectedLineRegex = r"(Binaerdatei \\verb\|%s\| nicht als Bild eingebunden)" \
                                    % (filename,)
                self.assertNotEqual(re.findall(expectedLineRegex, exportedCourseTexWithImages), [])

        self.do_login()
        _addImagesToCourse01()
        tarFile = self._getExportAsTar()
        _checkExportedFilenames(tarFile)

        exportedCourseTexWithImages = tarFile.extractfile("texexport_xa2011-1/course01/chap.tex").read().decode()
        _checkFilenamesInComment(exportedCourseTexWithImages)
        _checkFilenamesInIncludegraphics(exportedCourseTexWithImages)
        _checkFilenamesExpectedNotIncluded(exportedCourseTexWithImages)


class LocalExportScriptTest(unittest.TestCase):
    """Check whether the script to create a (LaTeX) export from a raw export
    works. This calls the exporter externally and does not require a dokuforge
    example instance."""

    testExportDir = "testData/texexport_txa2011-1"

    def testLocalExportScript(self):
        def _runLocalExport():
            self.assertFalse(os.path.isdir(self.testExportDir))
            with open(os.devnull, 'w') as devnull:
                subprocess.call("cd testData && tar xf dokuforge-export-static_test.tar.gz",
                                shell=True, stdout=devnull, stderr=devnull)
                subprocess.call("./localExport.sh testData/txa2011-1.tar.gz testData/dokuforge-export-static_test/",
                                shell=True, stdout=devnull, stderr=devnull)

        def _cleanUp():
            shutil.rmtree("testData/dokuforge-export-static_test")
            shutil.rmtree(self.testExportDir)

        def _verifyPseudoDokuforgeStaticFilesExist():
            # This is not part of the standard dokuforge-export-static,
            # but a different file expected in the dummy data used here.
            fileName = os.path.join(self.testExportDir, "someFile.txt")
            self.assertTrue(os.path.isfile(fileName))
            with open(fileName, 'r') as someFile:
                someFileContents = someFile.read()
                self.assertIn("Just some file ...", someFileContents)

        def _verifyInputDf2FileContents():
            for fileName in (os.path.join(self.testExportDir, "course01/input.df2"),
                             os.path.join(self.testExportDir, "course02/input.df2")):
                self.assertTrue(os.path.isfile(fileName))
                with open(fileName, 'r') as df2InputFile:
                    df2InputContents = df2InputFile.read()
                    self.assertIn("title", df2InputContents)
                    self.assertIn("page0", df2InputContents)
                    self.assertIn("page1", df2InputContents)

        def _verifyWarningContainsGitHash():
            with open(os.path.join(self.testExportDir, "WARNING"), 'r') as warningFile:
                warningContents = warningFile.read()
                currentGitRevision = subprocess.check_output("git rev-parse HEAD", shell=True).strip().decode()
                self.assertIn(currentGitRevision, warningContents)

        _runLocalExport()
        _verifyPseudoDokuforgeStaticFilesExist()
        _verifyInputDf2FileContents()
        _verifyWarningContainsGitHash()
        _cleanUp()


class CourseTests(DfTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="dokuforge").encode("ascii")
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
        self.tmpdir = tempfile.mkdtemp(prefix='dokuforge').encode("ascii")
        os.makedirs(os.path.join(self.tmpdir, b'example/legacy'))
        self.academy = Academy(os.path.join(self.tmpdir, b'example'), [])
        self.academy.createCourse('new01', 'erster neuer Kurs')
        self.academy.createCourse('new02', 'zweiter neuer Kurs')

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
        self.academy.getCourse('new01').delete()
        self.assertCourses([b'legacy', b'new02'])
        self.assertDeadCourses([b'new01'])

    def testDeleteLegacyCourse(self):
        self.academy.getCourse('legacy').delete()
        self.assertCourses([b'new01', b'new02'])
        self.assertDeadCourses([b'legacy'])

    def testCourseDeleteUndelete(self):
        self.academy.getCourse('new01').delete()
        self.assertDeadCourses([b'new01'])
        self.academy.getCourse('new01').undelete()
        self.assertCourses([b'legacy', b'new01', b'new02'])
        self.assertDeadCourses([])

class EstimatorTests(DfTestCase):
    def test_estimates(self):
        lipsum = "Lorem ipsum dolor sit amet. "

        estimate = Estimate.fromText(10*lipsum)
        self.assertAlmostEqual(estimate.pages,       0.056)
        self.assertAlmostEqual(estimate.ednotepages, 0.0)
        self.assertAlmostEqual(estimate.blobpages,   0.0)

        estimate = Estimate.fromTitle(4*lipsum)
        self.assertAlmostEqual(estimate.pages,       0.0648)
        self.assertAlmostEqual(estimate.ednotepages, 0.0)
        self.assertAlmostEqual(estimate.blobpages,   0.0)

        estimate = Estimate.fromEdnote("{"+10*lipsum+"}")
        self.assertAlmostEqual(estimate.pages,       0.0)
        self.assertAlmostEqual(estimate.ednotepages, 0.0564)
        self.assertAlmostEqual(estimate.blobpages,   0.0)

        estimate = Estimate.fromBlobs((None, None))
        self.assertAlmostEqual(estimate.pages,       0.0)
        self.assertAlmostEqual(estimate.ednotepages, 0.0)
        self.assertAlmostEqual(estimate.blobpages,   0.6666666666)

class DokuforgeMockTests(DfTestCase):
    def verify_idempotency(self, inp):
        inp2 = dfLineGroupParser(inp).toDF()
        inp3 = dfLineGroupParser(inp2).toDF()
        self.assertEqual(inp2, inp3, "original input was %r" % inp)

    def testParserIdempotency(self, rounds=100, minlength=10, maxlength=99):
        for _ in range(rounds):
            for l in range(minlength, maxlength):
                inp = "".join(random.choice("aA \n*[()]1.$<>&\"{}_\\-")
                              for _ in range(l))
                self.verify_idempotency(inp)

    def testParserIdempotency1(self):
        self.verify_idempotency('_a\n[[[\n\n"')

    def testHeadingHtmlEscape(self):
        out = dfLineGroupParser("[bad < html chars >]").toHtml().strip()
        self.assertEqual(out, "<h1>bad &lt; html chars &gt;</h1>")

    def testAuthorHtmlEscape(self):
        out = dfLineGroupParser("[ok]\n(bad < author >)").toHtml().strip()
        self.assertEqual(out, "<h1>ok</h1>\n<i>bad &lt; author &gt;</i>")

class ExporterTestStrings:
    """Input and expected output for testing exporter"""

    itemizeAndCo = [[r'- Text',
                     r'\begin{itemize}[flushleft,joinedup,packed]' + '\n' + r'\item Text' + '\n' + r'\end{itemize}'],
                    [r'-Text',
                     r'-Text'],
                    [r'- item' + '\n\n' + r'-nonitem',
                     r'\begin{itemize}[flushleft,joinedup,packed]' + '\n' + r'\item item' + '\n' + r'\end{itemize}' + '\n\n' + r'-nonitem'],
                    [r'1. item',
                     r'\begin{enumerate}[flushleft,joinedup,packed]' + '\n' + r'% 1' + '\n' + r'\item item' + '\n' + r'\end{enumerate}'] ]

    quotes = [ ['Wir haben Anf\\"uhrungszeichen "mitten" im Satz.',
                'Wir haben Anf\\"uhrungszeichen "`mitten"\' im Satz.'],
               ['"Am Anfang" des Texts',
                '"`Am Anfang"\' des Texts'],
               ['in der Mitte "vor Kommata", im Text',
                'in der Mitte "`vor Kommata"\', im Text'],
               ['und "am Ende".',
                'und "`am Ende"\'.'],
               ['"Vor und"\n"nach" Zeilenumbrüchen.',
                '"`Vor und"\' "`nach"\' Zeilenumbrüchen.'],
               ['Markus\' single quote',
                'Markus\\@\' single quote'],
               ['"Wow"-Effekt',
                '"`Wow"\'-Effekt'],
               ['Was laesst Menschen "aufbluehen"?',
                'Was laesst Menschen "`aufbluehen"\'?'],
               ['ei "(Ei" ei ("Ei" ei',
                'ei "`(Ei"\' ei ("`Ei"\' ei'],
               ['"Schoki"! "Cola"; "Wasser", "Nudeln": "Suppe")',
                '"`Schoki"\'! "`Cola"\'; "`Wasser"\', "`Nudeln"\': "`Suppe"\')'],
               ['"Yo!" "Whaaat?" "Boom." "Cola;" "Nudeln:" "Suppe)"',
                '"`Yo!"\' "`Whaaat?"\' "`Boom."\' "`Cola;"\' "`Nudeln:"\' "`Suppe)"\''],
               ['"Wasser,"',
                '"`Wasser,"\''],
               ['So "sollte es" sein. Und "$so$ ist $es$" hier.',
                'So "`sollte es"\' sein. Und \\@"`$so$ ist $es$\\@"\' hier.'],
               ['Bitte "ACRONYME" berücksichtigen.',
                'Bitte "`\\@\\acronym{ACRONYME}"\' berücksichtigen.'],
               ['"Altern der DNA"',
                '"`Altern der \\@\\acronym{DNA}"\''] ]

    abbreviation = [ [r'Von 3760 v.Chr. bis 2012 n.Chr. und weiter',
                      r'Von 3760\,v.\,Chr. bis 2012\,n.\,Chr. und weiter'],
                     [r'Es ist z.B. so, s.o., s.u., etc., dass wir, d.h.',
                      r'Es ist z.\,B. so, s.\,o., s.\,u., etc., dass wir, d.\,h.'],
                     [r'aber u.a. auch o.ä. wie o.Ä.',
                      r'aber u.\,a. auch o.\,ä. wie o.\,Ä.'],
                     [r'Keine erlaubet Abkuerzungen sind umgspr. und oBdA. im Exporter.',
                      r'Keine erlaubet Abkuerzungen sind umgspr. und oBdA. im Exporter.'],
                     # similar to above, but with spaces in input
                     [r'Von 3760 v. Chr. bis 2012 n. Chr. und weiter',
                      r'Von 3760\,v.\,Chr. bis 2012\,n.\,Chr. und weiter'],
                     [r'Es ist z. B. so, s. o., s. u., etc., dass wir,',
                      r'Es ist z.\,B. so, s.\,o., s.\,u., etc., dass wir,'],
                     [r'd. h., der Exporter bzw. oder ca. oder so.',
                      r'd.\,h., der Exporter bzw. oder ca. oder so.'],
                     [r'Aber u. a. auch o. ä. wie o. Ä.',
                      r'Aber u.\,a. auch o.\,ä. wie o.\,Ä.']]

    acronym = [ [r'Bitte ACRONYME wie EKGs anders setzen.',
                 r'Bitte \@\acronym{ACRONYME} wie \@\acronym{EKGs} anders setzen.'],
                [r'Unterscheide T-shirt und DNA-Sequenz.',
                 r'Unterscheide T-shirt und \@\acronym{DNA}-Sequenz.'],
                [r'Wenn 1D nicht reicht, nutze 2D oder 6D.',
                 r'Wenn 1\@\acronym{D} nicht reicht, nutze 2\@\acronym{D} oder' + '\n' + r'6\@\acronym{D}.'],
                [r'Wahlergebnis fuer die SPD: 9% (NRW).',
                 r'Wahlergebnis fuer die \@\acronym{SPD}: 9\,\% (\@\acronym{NRW}).'],
                [r'FDP? CDU! CSU. ÖVP.',
                 r'\@\acronym{FDP}? \@\acronym{CDU}! \@\acronym{CSU}. \@\acronym{ÖVP}.'],
                [r'Das ZNS.',
                 r'Das \@\acronym{ZNS}.'] ]

    emph = [ [r'wir heben _etwas_ hervor',
              r'wir heben \emph{etwas} hervor'],
             [r'wir heben _noch etwas_ hervor',
              r'wir heben \emph{noch etwas} hervor'],
             [r'wir heben _noch z.B. dies_ hervor',
              r'wir heben \emph{noch z.\,B. dies} hervor'],
             [r'wir heben _noch ETWAS mehr_ hervor',
              r'wir heben \emph{noch \@\acronym{ETWAS} mehr} hervor'],
             [r'wir _vergessen zu schließen.',
              r'wir \emph{vergessen zu schließen.}'],
             [r'wir _\machenUnfug_ hier',
              r'wir \emph{\@\forbidden\machenUnfug} hier'],
            ]

    escaping = [ [r'Forbid \mathbb and \dangerous outside math.',
                  r'Forbid \@\forbidden\mathbb and \@\forbidden\dangerous outside math.'],
                 [r'Do not allow $a \dangerous{b}$ commands!',
                  r'Do not allow $a \@\forbidden\dangerous{b}$ commands!'],
                 [r'\\ok, $\\ok$',
                  r'\\ok, $\\ok$'],
                 [r'$\\\bad$',
                  r'$\\\@\forbidden\bad$'],
                 [r'Escaping in math like $\evilmath$, but not $\mathbb C$',
                  r'Escaping in math like $\@\forbidden\evilmath$, but not $\mathbb C$'],
                 [r'$\circ$ $\cap\inf$ $\times$',
                  r'$\circ$ $\cap\inf$ $\times$' ],
                 [r'$a &= b$',
                  r'$a \@\forbidden\&= b$'],
                 [r'$$a &= b$$',
                  r'\begin{equation*}' + '\n' + r'a \@\forbidden\&= b' + '\n' + r'\end{equation*}'],
                 ['Trailing \\',
                  r'Trailing \@\backslash'],
                 [r'$Trailing \$',
                  r'$Trailing \@\backslash$'],
                 [r'f# ist eine Note',
                  r'f\@\# ist eine Note'],
                 [r'$a^b$ ist gut, aber a^b ist schlecht',
                  r'$a^b$ ist gut, aber a\@\caret{}b ist schlecht'],
                 [r'Heinemann&Co. ist vielleicht eine Firma',
                  r'Heinemann\@\&Co. ist vielleicht eine Firma'],
                 [r'10% sind ein Zehntel und mehr als 5 %.',
                  r'10\,\% sind ein Zehntel und mehr als 5\@\,\%.'],
                 [r'Geschweifte Klammern { muessen } escaped werden.',
                  r'Geschweifte Klammern \@\{ muessen \@\} escaped werden.'],
                 [r'Tilde~ist unklar. $Auch~hier$.',
                  r'Tilde\@~ist unklar. $Auch\@~hier$.'] ]

    mathSymbols = [ ['$\\'+i+'$', '$\\'+i+'$'] for i in allowedMathSymbolCommands ]

    mathEnvironments = [ [r'b $$\circ \cap \inf \times$$ e',
                          r'b' + '\n' + r'\begin{equation*}' + '\n' + r'\circ \cap \inf \times' + '\n' + r'\end{equation*}' + '\n' + r' e'],
                         [r'b $$' + '\n' + r'\circ \cap \inf \times' + '\n' + r'$$ e',
                          r'b' + '\n' + r'\begin{equation*}' + '\n' + r'\circ \cap \inf \times' + '\n' + r'\end{equation*}' + '\n' + r' e'],
                         [r'b $$' + '\n' + r'\begin{equation}a + b = c\end{equation}' + '\n' + r'$$ e',
                          r'b' + '\n' + r'\begin{equation}' + '\n' + r'a + b = c' + '\n' + r'\end{equation}' + '\n' + r' e'],
                         [r'b $$' + '\n' + r'\begin{equation*}a + b = c \end{equation*}' + '\n' + r'$$ e',
                          r'b' + '\n' + r'\begin{equation*}' + '\n' + r'a + b = c' + '\n' + r'\end{equation*}' + '\n' + r' e'],
                         [r'b $$' + '\n' + r'\begin{align}' + '\n' + r'a + b &= c \\' + '\n' + r'a - b &= d' + '\n' + r'\end{align}' + '\n' + r'$$ e',
                          r'b' + '\n' + r'\begin{align}' + '\n' + r'a + b &= c \\' + '\n' + r'a - b &= d' + '\n' + r'\end{align}' + '\n' + r' e'],
                         [r'b $$' + '\n' + r'\begin{align*}' + '\n' + r'a + b &= c \\' + '\n' + r'a - b &= d' + '\n' + r'\end{align*}' + '\n' + r'$$ e',
                          r'b' + '\n' + r'\begin{align*}' + '\n' + r'a + b &= c \\' + '\n' + r'a - b &= d' + '\n' + r'\end{align*}' + '\n' + r' e'],
                         [r'b $$' + '\n' + r'\begin{align}' + '\n' + r'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz &= c\\' + '\n' + r'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz &= d \end{align}' + '\n' + r'$$ e',
                          r'b' + '\n' + r'\begin{align}' + '\n' + r'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz &= c\\' + '\n' + r'abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyz &= d' + '\n' + r'\end{align}' + '\n' + r' e'],
                         [r'a $$' + '\n' + r'\begin{equation} b &= c \end{equation}' + '\n' + r'$$ d',
                          r'a' + '\n' + r'\begin{equation}' + '\n' + r'b \@\forbidden\&= c' + '\n' + r'\end{equation}' + '\n' + r' d'],
                         [r'b $$' + '\n' + r'\begin{equation}a + b &= c\end{equation}' + '\n' + r'$$ e',
                          r'b' + '\n' + r'\begin{equation}' + '\n' + r'a + b \@\forbidden\&= c' + '\n' + r'\end{equation}' + '\n' + r' e'],
                         [r'b $$' + '\n' + r'\begin{align}a + b \evilmath = c\end{align}' + '\n' + r'$$ e',
                          r'b' + '\n' + r'\begin{align}' + '\n' + r'a + b \@\forbidden\evilmath = c' + '\n' + r'\end{align}' + '\n' + r' e'],
                         [r'Bla $$' + '\n' + r'\begin{align}' + '\n' + r'a + b &= c\\' + '\n' + r'a - b &= d \end{align}' + '\n' + r'$$ Blub',
                          r'Bla' + '\n' + r'\begin{align}' + '\n' + r'a + b &= c\\' + '\n' + r'a - b &= d' + '\n' + r'\end{align}' + '\n' + r' Blub'],
                         [r'Matrix $\begin{pmatrix} a & b \\ c & d \end{pmatrix}$.',
                          r'Matrix $\@\forbidden\begin{pmatrix} a \@\forbidden\& b \\ c' + '\n' + r'\@\forbidden\& d \@\forbidden\end{pmatrix}$.'],
                         [r'Chemische Formel fuer $\ch{H3O+}$ protoniertes Wasser.',
                          r'Chemische Formel fuer $\ch{H3O+}$ protoniertes Wasser.'] ]

    evilUTF8 = [ [r'Bla … blub bloink.',
                  r'Bla~\@\dots{} blub bloink.'],
                 [r'Bla – blub — bloink.',
                  r'Bla \@-- blub \@--- bloink.'],
                 [r'Bla „deutsch“ “american” ”unusual“.',
                  r'Bla \@"`deutsch\@"'+'\''+r' \@"`american\@"'+'\''+r' \@"`unusual\@"'+'\''+r'.'],
                 [r'Bla «französisch» oder « französisch ».',
                  r'Bla \@"`französisch\@"'+'\''+r' oder \@\@"` französisch \@\@"`.'],
                 [r'Bla „(deutsch,“ “(american,” ”(unusual,“.',
                  r'Bla \@"`(deutsch,\@"'+'\''+r' \@"`(american,\@"'+'\''+r' \@"`(unusual,\@"'+'\''+r'.'],
                 [r'„$einsam$ $lonely$” $quote$“ here.',
                  r'\@"`$einsam$ $lonely$\@"'+'\''+r' $quote$\@"'+'\''+r' here.'],
                 [r'Bla »blub« bloink.',
                  r'Bla \@"`blub\@"'+'\''+r' bloink.'],
                 [r''+'\''+r'Bla'+'\''+r' ‚blub‘ ‚bloink’ ›blub‹ ‹bloink›.',
                  r'\@'+'\''+r'Bla\@'+'\''+r' \@'+'\''+r'blub\@'+'\''+r' \@'+'\''+r'bloink\@'+'\''+r' \@'+'\''+r'blub\@'+'\''+r' \@'+'\''+r'bloink\@'+'\''+r'.'],
                 [r'„‚Nested quotes‘”.',
                  '\@\@"`\@'+'\''+r'Nested quotes\@'+'\''+r'\@\@"`.'] ]

    _unicodeNonstandardSpaces = ( ' ',    # non-breaking space U+00A0
                                  ' ',    # en quad U+2000
                                  ' ',    # em quad U+2001
                                  ' ',    # en space U+2002
                                  ' ',    # em space U+2003
                                  ' ',    # 1/3 em space U+2004
                                  ' ',    # 1/4 em space U+2005
                                  ' ',    # 1/6 em space U+2006
                                  ' ',    # figure space U+2007
                                  ' ',    # punctuation space U+2008
                                  ' ',    # thin space U+2009
                                  ' ',    # hair space U+200A
                                  '​',    # zero width space U+200B
                                  ' ',    # narrow no-break space U+202F
                                  ' ',    # medium mathematical space (4/18 em) U+205F
                                  '﻿',    # zero-width non-breaking space U+FEFF
                                 )
    nonstandardSpace = [ ['x x',    # standard ASCII space
                          'x x' ] ] + \
                       [ [ f'x{i}x', r'x\@ x'] for i in _unicodeNonstandardSpaces ]

    pageReferences = [ [r'Auf S. 4 Abs. 3 in Art. 7 steht',
                        r'Auf \@S.\,4 \@Abs.\,3 in \@Art.\,7 steht'],
                       [r'Auf Seite 4 Absatz 3 in Artikel 7 steht',
                        r'Auf Seite~4 Absatz~3 in Artikel~7 steht'],
                       [r'Auf S.4-6 steht',
                        r'Auf \@S.\,4\@--6 steht'],
                       [r'Auf S.4--6 steht',
                        r'Auf \@S.\,4--6 steht'],
                       [r'Auf S. 4f steht',
                        r'Auf \@S.\,4\,f. steht'],
                       [r'S. 4 ff. besagt',
                        r'\@S.\,4\,ff. besagt'],
                       [r'Es fehlen Angaben zu S. Abs. Art.',
                        r'Es fehlen Angaben zu \@S. \@Abs. \@Art.'] ]

    spacing = [ ['A number range 6--9 is nice.',
                 'A number range 6--9 is nice.'],
                [r'6 -- 9 is as nice as 6-- 9, 6 --9 and 6 - 9 or 6- 9.',
                 r'6\@--9 is as nice as 6\@--9, 6\@--9 and 6\@--9 or 6\@--9.'],
                ['Now we do - with all due respect --, an intersperse.',
                 r'Now we do \@-- with all due respect \@--, an intersperse.'],
                [r'Followed by an afterthougt -- here it comes.',
                 r'Followed by an afterthougt \@-- here it comes.'],
                [r'Followed by an afterthougt---here it comes.',
                 r'Followed by an afterthougt\@---here it comes.'],
                [r'Here come some dots ...',
                 r'Here come some dots~\@\dots{}'],
                [r'Here come some dots...',
                 r'Here come some dots\@\dots{}'],
                [r'Dots in math $a_1,...,a_n$ should work without spacing.',
                 r'Dots in math $a_1,\@\dots{},a_n$ should work without spacing.'],
                [r'And dots ... in … the middle.',
                 r'And dots~\@\dots{} in~\@\dots{} the middle.'],
                [r'And dots...in the middle.',
                 r'And dots\@\dots{}in the middle.'],
                [r'And dots [...] for missing text.',
                 r'And dots [\@\ZitatEllipse] for missing text.'] ]

    lawReference = [ [r'In §§1ff. HGB steht',
                      r'In §§\,1\,ff. \@\acronym{HGB} steht'],
                     [r'In § 1 f. HGB steht',
                      r'In §\,1\,f. \@\acronym{HGB} steht'],
                     [r'In § 1 Abs. 1 HGB steht',
                      r'In §\,1 \@Abs.\,1 \@\acronym{HGB} steht'],
                     [r'In § 1 Absatz 1 Satz 2 HGB steht',
                      r'In §\,1 Absatz~1 Satz~2 \@\acronym{HGB} steht'],
                     [r'In §§ 10-15 HGB steht',
                      r'In §§\,10\@--15 \@\acronym{HGB} steht'],
                     [r'Ein verlorener § und noch ein §',
                      r'Ein verlorener \@§ und noch ein \@§'] ]

    numbers = [ [r'We have 10000, 2000 and 3000000 and -40000 and -5000.',
                 r'We have 10\,000, 2000 and 3\,000\,000 and \@$-$40\,000 and \@$-$5000.'],
                [r'We are in the 21. regiment and again in the 21.regiment.',
                 r'We are in the \@21. regiment and again in the \@21.regiment.'],
                [r'bis zu 30 000 Einwohner',
                 r'bis zu 30 000 Einwohner'],
                [r'Kennwort 0000 ist unsicher, 00000 auch, 0000000 nicht weniger',
                 r'Kennwort 0000 ist unsicher, 00\,000 auch, 0\,000\,000 nicht weniger'],
                [r'some 5,000 races',
                 r'some 5,000 races'],
                [r'pi ist 3,14159',
                 r'pi ist 3,14\,159'],  # this is not really what we want, but too rare and too complex to find an automatic solution
                [r'bla 2004-2006 blub',
                 r'bla 2004\@--2006 blub']
              ]

    dates = [ [r'The date is 19.5.2012 or 19. 10. 95 for good.',
               r'The date is \@19.\,5.\,2012 or \@19.\,10.\,95 for good.'] ]

    units = [ [r'Units: 21kg, 4MW, 1mV, 13-14TeV, 5°C.',
               r'Units: 21\,kg, 4\,MW, 1\,\@mV, 13\@--14\,\@TeV, 5\,°C.'],
              [r'Decimal number with unit or unicode prefix: 25,4mm and 1.2μm.',
               r'Decimal number with unit or unicode prefix: 25,4\,mm and 1.2\,μm.'],
              [r'Units: 21 kg, 4 MW, 1 mV , 13--14 TeV, 5 °C.',
               r'Units: 21\,kg, 4\,MW, 1\,\@mV , 13--14\,\@TeV, 5\,°C.'],
              [r'Decimal number with unit: 25,4 mm.',
               r'Decimal number with unit: 25,4\,mm.'],
              [r'Percentages like 5 % should be handled as nicely as 5%.',
               r'Percentages like 5\@\,\% should be handled as nicely as 5\,\%.'],
              [r'90° is a right angle.',
               r'90° is a right angle.'] ]

    code = [ [r'|increase(i)| increases |i|, by one.',
              r'\@\lstinline|increase(i)| increases \@\lstinline|i|, by one.'] ]

    urls = [ [r'http://www.google.de',
              r'\@\url{http://www.google.de}'],
             [r'(siehe http://www.google.de)',
              r'(siehe \@\url{http://www.google.de})'],
             [r'http://www.google.de bla',
              r'\@\url{http://www.google.de} bla'],
             [r'http://www.google.de www.bla.de',
              r'\@\url{http://www.google.de} \@\url{www.bla.de}'],
             [r'http://www.google.de' + '\n' + r'www.bla.de',
              r'\@\url{http://www.google.de} \@\url{www.bla.de}'],
             [r'https://duckduckgo.com/?q=find&ia=web',
              r'\@\url{https://duckduckgo.com/?q=find&ia=web}'],
             [r'https://www.bla.com. Sowie http://www.blub.org?',
              r'\@\url{https://www.bla.com}. Sowie \@\url{http://www.blub.org}?'],
             [r'https://commons.wikimedia.org/wiki/File:Barf%C3%BCsserArkade1.jpg', # note that % needs to be escaped (else starts comment)
              r'\@\url{https://commons.wikimedia.org/wiki/File:Barf\%C3\%BCsserArkade1.jpg}'],
             [r'https://commons.wikimedia.org/wiki/File:Barfuesser_Arkade1.jpg',
              r'\@\url{https://commons.wikimedia.org/wiki/File:Barfuesser_Arkade1.jpg}'],
             [r'auf www.bla.com lesen',
              r'auf \@\url{www.bla.com} lesen'],
             [r'siehe www.bla.com.',
              r'siehe \@\url{www.bla.com}.'],
             [r'Das www.ist_keine_hervorhebung.de!',
              r'Das \@\url{www.ist_keine_hervorhebung.de}!'],
             [r'http://www.bla.com/foo}\evilCommand',
              r'\@\url{http://www.bla.com/foo}\@\}\@\forbidden\evilCommand']
             ]

    sectionsAndAuthors = [ [r'[foo]' + '\n' + r'(bar)',
                            r'\section{foo}' + '\n' + r'\authors{bar}'],
                           [r'[[foo]]' + '\n\n' + r'(bar)',
                            r'\subsection{foo}' + '\n\n' + r'(bar)'] ]

    sectionsWithEmph = [ [r'[Ola Gjeilo: _Northern Lights_]',
                          r'\section{Ola Gjeilo: \emph{Northern Lights}}'],
                         [r'[_Mein BAMF_ -- aus dem Kabarett]',
                          r'\section{\emph{Mein \@\acronym{BAMF}} \@-- aus dem Kabarett}'],
                         [r'[Max Reger: _Es waren zwei Königskinder_ hier]',
                          r'\section{Max Reger: \emph{Es waren zwei Königskinder} hier}'],
                         [r'[[Ola Gjeilo: _Northern Lights_]]',
                          r'\subsection{Ola Gjeilo: \emph{Northern Lights}}'],
                         [r'[[_Mein BAMF_ -- aus dem Kabarett]]',
                          r'\subsection{\emph{Mein \@\acronym{BAMF}} \@-- aus dem Kabarett}'],
                         [r'[[Max Reger: _Es waren zwei Königskinder_ hier]]',
                          r'\subsection{Max Reger: \emph{Es waren zwei Königskinder} hier}']]

    sectionsWithOrdinals = [ [r'[1. Buch Mose]',
                              r'\section{\@1. Buch Mose}'] ]

    numericalScope = [ ['10\xb3 Meter sind ein km',
                        '10\xb3 Meter sind ein km'] ]

    codeAndLengthyParagraph = [ [r'Larem ipsum dolor sit amet |rhoncus| lerem ipsum dolor sit amet' + '\n' + r'lirem ipsum dolor sit amet lorem ipsum dolor sit amet' + '\n' + r'lurem ipsum dolor sit amet.' + '\n\n' + r'Und hier ist noch ein Absatz. Lorem ipsum dolor sit amet. Und so weiter.',
                                 r'Larem ipsum dolor sit amet \@\lstinline|rhoncus| lerem ipsum dolor sit' + '\n' + r'amet lirem ipsum dolor sit amet lorem ipsum dolor sit amet lurem ipsum' + '\n' + r'dolor sit amet.' + '\n\n' + r'Und hier ist noch ein Absatz. Lorem ipsum dolor sit amet. Und so' + '\n' + r'weiter.'] ]

    lengthyParagraph = [ ["""Zwei lange Absätze, aber durch Leerzeile getrennt. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume.

Da brauchen wir keinen Hinweis. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume.""",
                          """Zwei lange Absätze, aber durch Leerzeile getrennt. Franz jagt im
komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox
jumps over the lazy dog. Portez ce vieux whisky au juge blond qui
fume.

Da brauchen wir keinen Hinweis. Franz jagt im komplett verwahrlosten
Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog.
Portez ce vieux whisky au juge blond qui fume."""],

                         ["""Drei kurze Zeilen, jeweils ohne Leerzeilen dazwischen.
Falsches Üben von Xylophonmusik quält jeden größeren Zwerg.
Da brauchen wir auch keinen Hinweis.""",
                          """Drei kurze Zeilen, jeweils ohne Leerzeilen dazwischen. Falsches Üben
von Xylophonmusik quält jeden größeren Zwerg. Da brauchen wir auch
keinen Hinweis."""],

                         [r"""Lange Zeilen, jeweils ohne Leerzeilen dazwischen. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume.
Das sieht verdächtig aus. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume.
Hier brauchen wir Hinweise. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume.""",
                          r"""Lange Zeilen, jeweils ohne Leerzeilen dazwischen. Franz jagt im
komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox
jumps over the lazy dog. Portez ce vieux whisky au juge blond qui
fume.\@\@\@ Das sieht verdächtig aus. Franz jagt im komplett
verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over
the lazy dog. Portez ce vieux whisky au juge blond qui fume.\@\@\@
Hier brauchen wir Hinweise. Franz jagt im komplett verwahrlosten Taxi
quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez
ce vieux whisky au juge blond qui fume."""],

                         [r"""Erst eine lange Zeile, dann eine kurze, ohne Leerzeilen dazwischen. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume. Das sieht verdächtig aus. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume.
Franz jagt im komplett verwahrlosten Taxi quer durch Bayern.""",
                          r"""Erst eine lange Zeile, dann eine kurze, ohne Leerzeilen dazwischen.
Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick
brown fox jumps over the lazy dog. Portez ce vieux whisky au juge
blond qui fume. Das sieht verdächtig aus. Franz jagt im komplett
verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over
the lazy dog. Portez ce vieux whisky au juge blond qui fume.\@\@\@
Franz jagt im komplett verwahrlosten Taxi quer durch Bayern."""],

                         ["""Erst eine kurze Zeile, dann eine lange, ohne Leerzeilen dazwischen.
Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume. Das sieht verdächtig aus. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux whisky au juge blond qui fume. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern.""",
                          """Erst eine kurze Zeile, dann eine lange, ohne Leerzeilen
dazwischen.\@\@\@ Franz jagt im komplett verwahrlosten Taxi quer durch
Bayern. The quick brown fox jumps over the lazy dog. Portez ce vieux
whisky au juge blond qui fume. Das sieht verdächtig aus. Franz jagt im
komplett verwahrlosten Taxi quer durch Bayern. The quick brown fox
jumps over the lazy dog. Portez ce vieux whisky au juge blond qui
fume. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern."""],

                         [r"""Erst eine kurze Zeile, dann eine lange mit Mathematik.
$z$ Franz jagt im komplett verwahrlosten Taxi quer durch Bayern $x$ The quick brown fox jumps over the lazy dog $x$ Portez ce vieux whisky au juge blond qui fume $x$ Das sieht verdächtig aus $x$ Franz jagt im komplett verwahrlosten Taxi quer durch Bayern $x$ The quick brown fox jumps over the lazy dog $x$ Portez ce vieux whisky au juge blond qui fume $x$ Franz jagt im komplett verwahrlosten Taxi quer durch Bayern.""",
                          r"""Erst eine kurze Zeile, dann eine lange mit Mathematik.\@\@\@ $z$ Franz
jagt im komplett verwahrlosten Taxi quer durch Bayern $x$ The quick
brown fox jumps over the lazy dog $x$ Portez ce vieux whisky au juge
blond qui fume $x$ Das sieht verdächtig aus $x$ Franz jagt im komplett
verwahrlosten Taxi quer durch Bayern $x$ The quick brown fox jumps
over the lazy dog $x$ Portez ce vieux whisky au juge blond qui fume
$x$ Franz jagt im komplett verwahrlosten Taxi quer durch Bayern."""],

                         ["""Kurze und lange Zeilen mit Leerzeilen dazwischen.

Bla blub. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. Bla blub. The quick brown fox jumps over the lazy dog. Bla blub. Portez ce vieux whisky au juge blond qui fume. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern. Bla blub. The quick brown fox jumps over the lazy dog. Bla blub. Portez ce vieux whisky au juge blond qui fume.

Das sieht unverdächtig aus.""",
                          """Kurze und lange Zeilen mit Leerzeilen dazwischen.

Bla blub. Franz jagt im komplett verwahrlosten Taxi quer durch Bayern.
Bla blub. The quick brown fox jumps over the lazy dog. Bla blub.
Portez ce vieux whisky au juge blond qui fume. Franz jagt im komplett
verwahrlosten Taxi quer durch Bayern. Bla blub. The quick brown fox
jumps over the lazy dog. Bla blub. Portez ce vieux whisky au juge
blond qui fume.

Das sieht unverdächtig aus."""],
]

    ednoteEscape = [ [r"""before

{{

Bobby Tables...

\end{ednote}

\herebedragons

}}

after""",
r"""before

\begin{ednote}

Bobby Tables...

\@|end{ednote}

\herebedragons

\end{ednote}

after""" ] ]

    multilineCaptions = [ [r'Dies ist eine Bildunterschrift.' + '\n\n' + r'Sie soll zwei Absätze haben.',
                           r'Dies ist eine Bildunterschrift.\@\@\@' + '\n' + r'Sie soll zwei Absätze haben.' ] ]

class ExporterTestCases:
    """
    Which tests should be run for the separate parsers?
    """
    testsEverywhere = [ ExporterTestStrings.quotes,
                        ExporterTestStrings.abbreviation,
                        ExporterTestStrings.acronym,
                        ExporterTestStrings.emph,
                        ExporterTestStrings.escaping,
                        ExporterTestStrings.mathSymbols,
                        ExporterTestStrings.mathEnvironments,
                        ExporterTestStrings.evilUTF8,
                        ExporterTestStrings.nonstandardSpace,
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
                    ExporterTestStrings.codeAndLengthyParagraph ]

    lineGroupTests = testsInText + \
                     [ ExporterTestStrings.sectionsAndAuthors,
                       ExporterTestStrings.sectionsWithEmph,
                       ExporterTestStrings.sectionsWithOrdinals,
                       ExporterTestStrings.lengthyParagraph ]

    titleTests = testsEverywhere

    captionTests = [[[i, j.replace('\n\n', '\\@\\@\\@\n')] for i, j in k] for k in testsInText] + \
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
