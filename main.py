#!/usr/bin/env python
# -*- coding: utf-8 -*-

import jinja2
import random
import os
import sqlite3
import copy
import re
import sys
import urllib
import ConfigParser
from cStringIO import StringIO
import werkzeug.utils
from werkzeug.wrappers import Request, Response
import werkzeug.exceptions
import werkzeug.routing
import operator
from wsgiref.simple_server import make_server
from wsgitools.applications import StaticFile
from wsgitools.middlewares import TracebackMiddleware, SubdirMiddleware
from wsgitools.scgi.asynchronous import SCGIServer as AsynchronousSCGIServer
from wsgitools.scgi.forkpool import SCGIServer as ForkpoolSCGIServer
# import other parts of Dokuforge
import academy
import course
import storage
import user

try:
    import hashlib
    getmd5 = hashlib.md5
except ImportError:
    import md5
    getmd5 = md5.new

sysrand = random.SystemRandom()

def gensid(bits=64):
    """
    @type bits: int
    @param bits: randomness in bits of the resulting string
    @rtype: str
    @returns: a random string
    """
    return "%x" % random.getrandbits(bits)

class SessionHandler:
    """Associate users with session ids in a DBAPI2 database."""
    create_table = "CREATE TABLE IF NOT EXISTS sessions " + \
                   "(sid TEXT, user TEXT, UNIQUE(sid));"
    cookie_name = "sid"

    def __init__(self, db, request, response):
        """
        @param db: a DBAPI2 database that has a sessions table as described
                in the create_table class variable
        @type request: werkzeug.wrappers.Request
        @type response: werkzeug.wrappers.Response
        """
        self.db = db
        self.cur = db.cursor()
        self.response = response
        self.sid = request.cookies.get(self.cookie_name)

    def get(self):
        """Find a user session.
        @rtype: unicode or None
        @returns: a username or None
        """
        if self.sid is None:
            return None
        self.cur.execute("SELECT user FROM sessions WHERE sid = ?;",
                         (self.sid.decode("utf8"),))
        results = self.cur.fetchall()
        if len(results) != 1:
            return None
        assert isinstance(results[0][0], unicode)
        return results[0][0]

    def set(self, username):
        """Initiate a user session.
        @type username: unicode
        """
        if self.sid is None:
            self.sid = gensid()
            self.response.set_cookie(self.cookie_name, self.sid)
        self.cur.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?);",
                         (self.sid.decode("utf8"), username))
        self.db.commit()

    def delete(self):
        """Delete a user session.
        @rtype: [(str, str)]
        @returns: a list of headers to be sent with the http response
        """
        if self.sid is not None:
            self.cur.execute("DELETE FROM sessions WHERE sid = ?;",
                             (self.sid.decode("utf8"),))
            self.db.commit()
            self.response.delete_cookie(self.cookie_name)

class RequestState:
    def __init__(self, request, sessiondb, userdb, mapadapter):
        self.request = request
        self.response = Response()
        self.sessionhandler = SessionHandler(sessiondb, request, self.response)
        self.userdb = userdb
        self.user = copy.deepcopy(self.userdb.db.get(self.sessionhandler.get()))
        self.mapadapter = mapadapter
        self.params = None # set later in Application.render

    def login(self, username):
        self.user = copy.deepcopy(self.userdb.db[username])
        self.sessionhandler.set(self.user.name)

    def logout(self):
        self.user = None
        self.sessionhandler.delete()

class TemporaryRequestRedirect(werkzeug.exceptions.HTTPException,
                               werkzeug.routing.RoutingException):
    code = 307

    def __init__(self, new_url):
        werkzeug.routing.RoutingException.__init__(self, new_url)
        self.new_url = new_url

    def get_response(self, environ):
        return werkzeug.utils.redirect(self.new_url, self.code)

class CheckError(StandardError):
    def __init__(self, msg, exp):
        assert isinstance(msg, unicode)
        assert isinstance(exp, unicode)
        self.message = msg
        self.explanation = exp
    def __str__(self):
        return self.message

class IdentifierConverter(werkzeug.routing.BaseConverter):
    regex = '[a-z][a-zA-Z0-9-]{0,199}'

class Application:
    def __init__(self, userdb, groupstore, acapath, templatepath, stylepath,
                 sessiondbpath=":memory:"):
        assert isinstance(acapath, str)
        assert isinstance(templatepath, str)
        assert isinstance(stylepath, str)
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader(templatepath))
        self.sessiondb = sqlite3.connect(sessiondbpath)
        cur = self.sessiondb.cursor()
        cur.execute(SessionHandler.create_table)
        self.sessiondb.commit()
        self.userdb = userdb
        self.acapath = acapath
        self.templatepath = templatepath
        self.stylepath = stylepath
        self.groupstore = groupstore
        rule = werkzeug.routing.Rule
        self.routingmap = werkzeug.routing.Map([
            rule("/", methods=("GET", "HEAD"), endpoint="start"),
            rule("/login", methods=("POST",), endpoint="login"),
            rule("/logout", methods=("POST",), endpoint="logout"),
            rule("/docs/", methods=("GET", "HEAD"), endpoint="index"),
            rule("/admin/", methods=("GET", "HEAD"), endpoint="admin"),
            rule("/admin/!save", methods=("POST",), endpoint="adminsave"),
            rule("/createacademy", methods=("GET", "HEAD"),
                 endpoint="createacademyquiz"),
            rule("/createacademy", methods=("POST",),
                 endpoint="createacademy"),
            rule("/groups/", methods=("GET", "HEAD"), endpoint="groups"),
            rule("/groups/!save", methods=("POST",),
                 endpoint="groupssave"),
            rule("/style/", methods=("GET", "HEAD"),
                 endpoint="styleguide"),
            rule("/style/<identifier:topic>", methods=("GET", "HEAD"),
                 endpoint="styleguidetopic"),
            rule("/groups/<identifier:group>", methods=("GET", "HEAD"),
                 endpoint="groupindex"),

            # academy specific pages
            rule("/docs/<identifier:academy>/", methods=("GET", "HEAD"),
                 endpoint="academy"),
            rule("/docs/<identifier:academy>/!createcourse",
                 methods=("GET", "HEAD"), endpoint="createcoursequiz"),
            rule("/docs/<identifier:academy>/!createcourse",
                 methods=("POST",), endpoint="createcourse"),
# not yet implemented
#            rule("/docs/<identifier:academy>/!export", methods=("GET", "HEAD"),
#                 endpoint="export"),
            rule("/docs/<identifier:academy>/!groups", methods=("GET", "HEAD"),
                 endpoint="academygroups"),
            rule("/docs/<identifier:academy>/!groups", methods=("POST",),
                 endpoint="academygroupssave"),
            rule("/docs/<identifier:academy>/!title", methods=("GET", "HEAD"),
                 endpoint="academytitle"),
            rule("/docs/<identifier:academy>/!title", methods=("POST",),
                 endpoint="academytitlesave"),

            # course-specific pages
            rule("/docs/<identifier:academy>/<identifier:course>/",
                 methods=("GET", "HEAD"), endpoint="course"),
            rule("/docs/<identifier:academy>/<identifier:course>/!createpage",
                 methods=("POST",), endpoint="createpage"),
            rule("/docs/<identifier:academy>/<identifier:course>/!deadpages",
                 methods=("GET", "HEAD"), endpoint="showdeadpages"),
            rule("/docs/<identifier:academy>/<identifier:course>/!moveup",
                 methods=("POST",), endpoint="moveup"),
            rule("/docs/<identifier:academy>/<identifier:course>/!relink",
                 methods=("POST",), endpoint="relink"),
            rule("/docs/<identifier:academy>/<identifier:course>/!raw",
                 methods=("GET", "HEAD"), endpoint="raw"),
            rule("/docs/<identifier:academy>/<identifier:course>/!title",
                 methods=("GET", "HEAD"), endpoint="coursetitle"),
            rule("/docs/<identifier:academy>/<identifier:course>/!title",
                 methods=("POST",), endpoint="coursetitlesave"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/",
                 methods=("GET", "HEAD"), endpoint="page"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!rcs",
                 methods=("GET", "HEAD"), endpoint="rcs"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!edit",
                 methods=("GET", "HEAD"), endpoint="edit"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!save",
                 methods=("POST",), endpoint="save"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!delete",
                 methods=("POST",), endpoint="delete"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!deadblobs",
                 methods=("GET", "HEAD"), endpoint="showdeadblobs"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!relinkblob",
                 methods=("POST",), endpoint="relinkblob"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!addblob",
                 methods=("GET", "HEAD"), endpoint="addblob"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!attachblob",
                 methods=("POST",), endpoint="attachblob"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/<int:blob>/",
                 methods=("GET", "HEAD"), endpoint="showblob"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/<int:blob>/!md5",
                 methods=("GET", "HEAD"), endpoint="md5blob"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/<int:blob>/!download",
                 methods=("GET", "HEAD"), endpoint="downloadblob"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/<int:blob>/!edit",
                 methods=("GET", "HEAD"), endpoint="editblob"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/<int:blob>/!edit",
                 methods=("POST",), endpoint="saveblob"),
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/<int:blob>/!delete",
                 methods=("POST",), endpoint="blobdelete"),
        ], converters=dict(identifier=IdentifierConverter))

    def buildurl(self, rs, name, kwargs):
        finalparams = {}
        ## the parameters were saved in Application.render
        params = rs.params
        params.update(kwargs)
        for key, value in rs.params.items():
            if self.routingmap.is_endpoint_expecting(name, key):
                if key == 'academy' or key == 'course':
                    finalparams[key] = value.name
                else:
                    finalparams[key] = value
        return rs.mapadapter.build(name, finalparams)

    def getAcademy(self, name, user=None):
        """
        @type name: unicode
        @type user: None or User
        @rtype: Academy
        """
        assert isinstance(name, unicode)
        name = name.encode("utf8")
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            raise werkzeug.exceptions.NotFound()
        if not os.path.isdir(os.path.join(self.acapath, name)):
            raise werkzeug.exceptions.NotFound()
        aca = academy.Academy(os.path.join(self.acapath, name))
        if user is not None and not user.allowedRead(aca):
            raise werkzeug.exceptions.Forbidden()
        return aca

    def getCourse(self, aca, coursename, user=None):
        """
        @type aca: Academy
        @type coursename: unicode
        @type user: None or User
        @rtype: Course
        """
        assert isinstance(coursename, unicode)
        c = aca.getCourse(coursename) # checks name
        if c is None:
            raise werkzeug.exceptions.NotFound()
        if user is not None and not user.allowedRead(aca, c):
            raise werkzeug.exceptions.Forbidden()
        return c

    def createAcademy(self, name, title, groups):
        """
        @type name: unicode
        @type title: unicode
        @rtype: None or Academy
        """
        assert isinstance(name, unicode)
        assert isinstance(title, unicode)
        assert all(isinstance(group, unicode) for group in groups)
        name = name.encode("utf8")
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            return None
        path = os.path.join(self.acapath, name)
        if os.path.exists(path):
            return None
        if len(groups) == 0:
            return None
        allgroups = self.listGroups()
        for group in groups:
            if not group in allgroups:
                return None
        os.makedirs(path)
        aca = academy.Academy(path)
        aca.settitle(title)
        aca.setgroups(groups)
        return aca

    def listAcademies(self):
        """
        @rtype: [Academy]
        """
        ret = [self.getAcademy(p.decode("utf8"))
               for p in os.listdir(self.acapath)]
        ret.sort(key=operator.attrgetter('name'))
        return ret

    def listGroups(self):
        try:
            config = ConfigParser.SafeConfigParser()
            config.readfp(StringIO(self.groupstore.content()))
        except ConfigParser.ParsingError as err:
            return {}
        ret = {}
        for group in config.sections():
            ret[group.decode("utf8")] = config.get(group, 'title').decode("utf8")
        return ret

    @Request.application
    def __call__(self, request):
        mapadapter = self.routingmap.bind_to_environ(request.environ)
        rs = RequestState(request, self.sessiondb, self.userdb, mapadapter)
        try:
            endpoint, args = mapadapter.match()
            return getattr(self, "do_%s" % endpoint)(rs, **args)
        except werkzeug.routing.HTTPException, e:
            return e

    def check_login(self, rs):
        if rs.user is None:
            raise TemporaryRequestRedirect(rs.request.url_root)

    def do_file(self, rs, filestore, template, extraparams=dict()):
        """
        @type rs: RequestState
        @type filestore: Storage
        @type template: str
        @type extraparams: dict
        """
        assert isinstance(template, str)
        version, content = filestore.startedit()
        return self.render_file(rs, template, version.decode("utf8"),
                                content.decode("utf8"), extraparams=extraparams)

    def do_filesave(self, rs, filestore, template, checkhook=None,
                    savehook=None, extraparams=dict()):
        userversion = rs.request.form["revisionstartedwith"]
        usercontent = rs.request.form["content"]
        if not checkhook is None:
            try:
                checkhook(usercontent)
            except CheckError as err:
                return self.render_file(rs, template, userversion, usercontent,
                                        ok=False, error = err,
                                        extraparams=extraparams)
        ok, version, content = filestore.endedit(userversion.encode("utf8"),
                usercontent.encode("utf8"), user=rs.user.name.encode("utf8"))
        version = version.decode("utf8")
        content = content.decode("utf8")
        if not savehook is None:
            savehook()
        if not ok:
            return self.render_file(rs, template, version, content, ok=False,
                                    error = CheckError(u"Es ist ein Konflikt mit einer anderen &Auml;nderung aufgetreten!", u"Bitte l&ouml;se den Konflikt auf und speichere danach erneut."),
                                    extraparams=extraparams)
        return self.render_file(rs, template, version, content, ok=True,
                                extraparams=extraparams)

    def do_start(self, rs):
        if rs.user is None:
            return self.render_start(rs)
        return self.render_index(rs)

    def do_login(self, rs):
        # FIXME: return proper error pages
        rs.response.headers.content_type = "text/plain"
        try:
            username = rs.request.form["username"]
            password = rs.request.form["password"]
            rs.request.form["submit"] # just check for existence
        except KeyError:
            rs.response.data = "missing form fields"
            return rs.response
        if not self.userdb.checkLogin(username, password):
            rs.response.data = "wrong password"
            return rs.response
        rs.login(username)
        return self.render_index(rs)

    def do_logout(self, rs):
        rs.logout()
        return self.render_start(rs)

    def do_index(self, rs):
        self.check_login(rs)
        return self.render_index(rs, None)

    def do_groupindex(self, rs, group=None):
        self.check_login(rs)
        return self.render_index(rs, group)

    def do_academy(self, rs, academy = None):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        return self.render_academy(rs, aca)

    def do_course(self, rs, academy = None, course = None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        return self.render_course(rs, aca, c)

    def do_showdeadpages(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_deadpages(rs, aca, c)

    def do_showdeadblobs(self, rs, academy=None, course=None, page=None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_deadblobs(rs, aca, c, page)

    def do_createcoursequiz(self, rs, academy=None):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.render_createcoursequiz(rs, aca)

    def do_createcourse(self, rs, academy=None):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        name = rs.request.form["name"]
        title = rs.request.form["title"]
        if aca.createCourse(name, title):
            return self.render_academy(rs, aca)
        else:
            return self.render_createcoursequiz(rs, aca, name=name,
                                                title=title, ok=False,
                                                error = CheckError(u"Die Kurserstellung war nicht erfolgreich.", u"Bitte die folgenden Angaben korrigieren."))

    def do_createacademyquiz(self, rs):
        self.check_login(rs)
        if not rs.user.mayCreate():
            return werkzeug.exceptions.Forbidden()
        return self.render_createacademyquiz(rs)

    def do_createacademy(self, rs):
        self.check_login(rs)
        if not rs.user.mayCreate():
            return werkzeug.exceptions.Forbidden()
        name = rs.request.form["name"]
        title = rs.request.form["title"]
        groups = rs.request.form["groups"].split()
        if self.createAcademy(name, title, groups):
            return self.render_index(rs)
        else:
            return self.render_createacademyquiz(rs, name=name,
                                                 title=title,
                                                 groups=rs.request.form["groups"],
                                                 ok=False,
                                                 error = CheckError(u"Die Akademieerstellung war nicht erfolgreich.", u"Bitte die folgenden Angaben korrigieren."))

    def do_styleguide(self, rs):
        return self.do_styleguidetopic(rs, u"index")

    def do_styleguidetopic(self, rs, topic=None):
        assert isinstance(topic, unicode)
        topic = topic.encode("utf8")
        if not topic in os.listdir(os.path.join(self.templatepath,
                                                self.stylepath)):
            raise werkzeug.exception.NotFound()
        return self.render_styleguide(rs, topic)

    def do_createpage(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.newpage(user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_delete(self, rs, academy=None, course=None, page=None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.delpage(page, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_blobdelete(self, rs, academy=None, course=None, page=None, blob=None):
        assert academy is not None and course is not None and page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.delblob(blob, user=rs.user.name)
        return self.render_show(rs, aca, c, page)

    def do_relink(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        numberstr = rs.request.form["number"]
        try:
            number = int(numberstr)
        except ValueError:
            number = 0
        c.relink(number, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_relinkblob(self, rs, academy=None, course=None, page=None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        numberstr = rs.request.form["number"]
        try:
            number = int(numberstr)
        except ValueError:
            number = 0
        c.relinkblob(number, page, user=rs.user.name)
        return self.render_show(rs, aca, c, page)

    def do_showblob(self, rs, academy=None, course=None, page=None, blob=None):
        assert academy is not None and course is not None and page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        theblob = c.getmetablob(blob)
        return self.render_showblob(rs, aca, c, page, blob, theblob)

    def do_editblob(self, rs, academy=None, course=None, page=None, blob=None):
        assert academy is not None and course is not None and page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        theblob = c.getmetablob(blob)
        return self.render_editblob(rs, aca, c, page, blob, theblob)


    def do_saveblob(self, rs, academy=None, course=None, page=None, blob=None):
        assert academy is not None and course is not None and page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()

        newlabel = rs.request.form["label"]
        newcomment = rs.request.form["comment"]
        newname = rs.request.form["name"]

        # we omit error handling here, since it seems unlikely, that two
        # changes for one blob's metadata conflict
        c.modifyblob(blob, newlabel, newcomment, newname, rs.user.name)
        theblob = c.getmetablob(blob)

        issaveshow = "saveshow" in rs.request.form
        if issaveshow:
            return self.render_showblob(rs, aca, c, page, blob, theblob)
        return self.render_editblob(rs, aca, c, page, blob, theblob)


    def do_md5blob(self, rs, academy=None, course=None, page=None, blob=None):
        assert academy is not None and course is not None and page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        theblob = c.getblob(blob)
        h = getmd5()
        h.update(theblob.data)
        blobhash = h.hexdigest()
        return self.render_showblob(rs, aca, c, page, blob, theblob, blobhash=blobhash)

    def do_downloadblob(self, rs, academy=None, course=None, page=None, blob=None):
        assert academy is not None and course is not None and page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/octet-stream"
        theblob = c.getblob(blob)
        rs.response.data = theblob.data
	rs.response.headers['Content-Disposition'] = "attachment; filename=%s" % theblob.filename
        return rs.response

    def do_rcs(self, rs, academy=None, course=None, page=None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/octet-stream"
        rs.response.data = c.getrcs(page)
	rs.response.headers['Content-Disposition'] = "attachment; filename=%d,v" % (page)
        return rs.response

    def do_raw(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/octet-stream"
        rs.response.data = c.export()
	rs.response.headers['Content-Disposition'] = "attachment; filename=%s_%s.tar" % (aca.name, c.name)
        return rs.response

    def do_moveup(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        numberstr = rs.request.form["number"]
        try:
            number = int(numberstr)
        except ValueError:
            number = 0
        c.swappages(number, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_page(self, rs, academy = None, course = None, page = None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        return self.render_show(rs, aca, c, page)

    def do_edit(self, rs, academy = None, course = None, page = None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        version, content = c.editpage(page)
        return self.render_edit(rs, aca, c, page, version, content)

    def do_addblob(self, rs, academy = None, course = None, page = None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_addblob(rs, aca, c, page)

    def do_attachblob(self, rs, academy = None, course = None, page = None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()

        usercomment = rs.request.form["comment"]
        userlabel = rs.request.form["label"]
        # a FileStorage is sufficiently file-like for store
        usercontent = rs.request.files["content"]

        if re.match('^[a-z0-9]{1,200}$', userlabel) is None:
            blob = c.attachblob(page, usercontent, comment=usercomment,
                            label=u"somefig", user=rs.user.name)
            theblob = c.getmetablob(blob)
            return self.render_editblob(rs, aca, c, page, blob, theblob, ok=False,
                                       error=CheckError(u"K&uuml;rzel falsch formatiert!",
                                                        u"Bitte korrigeren und speichern."))
        return self.render_show(rs, aca, c, page)

    def do_save(self, rs, academy = None, course = None, page = None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()

        userversion = rs.request.form["revisionstartedwith"]
        usercontent = rs.request.form["content"]

        ok, version, content = c.savepage(page, userversion, usercontent,
                                          user=rs.user.name)

        issaveshow = "saveshow" in rs.request.form
        if ok and issaveshow:
            return self.render_show(rs, aca, c, page, saved=True)

        return self.render_edit(rs, aca, c, page, version, content, ok=ok)

    def do_academygroups(self, rs, academy=None):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, storage.Storage(aca.path,"groups"),
                            "academygroups.html", extraparams={'academy': aca})

    def validateGroups(self, groupstring):
        """
        @type groupstring: unicode
        """
        assert isinstance(groupstring, unicode)
        groups = groupstring.split()
        if len(groups) == 0:
            raise CheckError(u"Keine Gruppen gefunden!",
                             u"Jede Akademie muss mindestens einer Gruppe angeh&ouml;ren. Bitte korrigieren und erneut versuchen.")
        for g in groups:
            if g not in self.listGroups():
                raise CheckError(u"Nichtexistente Gruppe gefunden!",
                                 u"Bitte korrigieren und erneut versuchen.")

    def do_academygroupssave(self, rs, academy=None):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, storage.Storage(aca.path,"groups"),
                                "academygroups.html",
                                checkhook = self.validateGroups,
                                extraparams={'academy': aca})

    def do_academytitle(self, rs, academy=None):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, storage.Storage(aca.path,"title"),
                            "academytitle.html", extraparams={'academy': aca})

    def do_academytitlesave(self, rs, academy=None):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, storage.Storage(aca.path,"title"),
                                "academytitle.html", extraparams={'academy': aca})

    def do_coursetitle(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, storage.Storage(c.path,"title"),
                            "coursetitle.html", extraparams={'academy': aca,
                                                              'course': c})

    def do_coursetitlesave(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, storage.Storage(c.path,"title"),
                                "coursetitle.html", extraparams={'academy': aca,
                                                                 'course': c})

    def do_admin(self, rs):
        self.check_login(rs)
        if not rs.user.isAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, self.userdb.storage, "admin.html")

    def tryConfigParser(self, content):
        """
        @type content: unicode
        """
        assert isinstance(content, unicode)
        try:
            config = ConfigParser.SafeConfigParser()
            config.readfp(StringIO(content.encode("utf8")))
        except ConfigParser.ParsingError as err:
            raise CheckError(u"Es ist ein Parser Error aufgetreten!",
                             u"Der Fehler lautetete: " + err.message + \
                             u". Bitte korrigiere ihn und speichere erneut.")

    def do_adminsave(self, rs):
        self.check_login(rs)
        if not rs.user.isAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, self.userdb.storage, "admin.html",
                                checkhook = self.tryConfigParser,
                                savehook = self.userdb.load)

    def do_groups(self, rs):
        self.check_login(rs)
        if not rs.user.isSuperAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, self.groupstore, "groups.html")

    def do_groupssave(self, rs):
        self.check_login(rs)
        if not rs.user.isSuperAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, self.groupstore, "groups.html",
                                checkhook = self.tryConfigParser)

    def render_start(self, rs):
        return self.render("start.html", rs)

    def render_styleguide(self, rs, topic):
        params= dict(
            topic = topic,
            includepath = self.stylepath + topic
            )
        return self.render("style.html", rs, params)

    def render_edit(self, rs, theacademy, thecourse, thepage, theversion, thecontent, ok=None):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        @type thepage: int
        @type theversion: unicode
        @type thecontent: unicode
        """
        assert isinstance(theversion, unicode)
        assert isinstance(thecontent, unicode)
        params= dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            content=thecontent, ## Note: must use the provided content, as it has to fit with the version
            version=theversion,
            ok=ok)
        return self.render("edit.html", rs, params)


    def render_index(self, rs, group = None):
        if group is None:
            group = rs.user.defaultGroup()
        params = dict(
            academies=map(academy.AcademyLite, self.listAcademies()),
            allgroups = self.listGroups(),
            group = group)
        return self.render("index.html", rs, params)

    def render_academy(self, rs, theacademy):
        return self.render("academy.html", rs,
                           dict(academy=academy.AcademyLite(theacademy)))

    def render_deadblobs(self, rs, theacademy, thecourse, thepage):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            blobs=[thecourse.getmetablob(i) for i in thecourse.listdeadblobs()]
)
        return self.render("deadblobs.html", rs, params)

    def render_deadpages(self, rs, theacademy, thecourse):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse))
        return self.render("dead.html", rs, params)

    def render_course(self, rs, theacademy, thecourse):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse))
        return self.render("course.html", rs, params)

    def render_addblob(self, rs, theacademy, thecourse, thepage, comment="",
                       label="", ok=None, error=None):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            comment=comment,
            label=label,
            error=error
            )
        return self.render("addblob.html", rs, params)

    def render_showblob(self, rs, theacademy, thecourse, thepage, blobnr,
                        theblob, blobhash=None):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            blob=blobnr,
            theblob=theblob,
            blobhash=blobhash)
        return self.render("showblob.html", rs, params)

    def render_editblob(self, rs, theacademy, thecourse, thepage, blobnr,
                        theblob, ok=None, error=None):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            blobnr=blobnr,
            blob=theblob,
            ok=ok,
            error=error
            )
        return self.render("editblob.html", rs, params)


    def render_createcoursequiz(self, rs, theacademy, name=u'', title=u'',
                                ok=None, error=None):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type name: unicode
        @type title: unicode
        @type ok: None or Boolean
        @type error: None or CheckError
        """
        assert isinstance(name, unicode)
        assert isinstance(title, unicode)
        params = dict(academy=academy.AcademyLite(theacademy),
                      name=name,
                      title=title,
                      ok=ok,
                      error=error)
        return self.render("createcoursequiz.html", rs, params)

    def render_createacademyquiz(self, rs, name=u'', title=u'', groups=u'',
                                 ok=None, error=None):
        """
        @type rs: RequestState
        @type name: unicode
        @type title: unicode
        @type groups: unicode
        @type ok: None or Boolean
        @type error: None or CheckError
        """
        assert isinstance(name, unicode)
        assert isinstance(title, unicode)
        assert isinstance(groups, unicode)
        params = dict(name=name,
                      title=title,
                      groups=groups,
                      ok=ok,
                      error=error)
        return self.render("createacademyquiz.html", rs, params)

    def render_show(self, rs, theacademy, thecourse,thepage, saved=False):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            content=thecourse.showpage(thepage),
            saved=saved,
            blobs=[thecourse.getmetablob(i) for i in thecourse.listblobs(thepage)]
            )
        return self.render("show.html", rs, params)

    def render_file(self, rs, templatename, theversion, thecontent, ok=None,
                    error=None, extraparams=dict()):
        """
        @type rs: RequestState
        @type templatename: str
        @type theversion: unicode
        @type thecontent: unicode
        @type ok: None or Booleon
        @type error: None or CheckError
        @type extraparams: dict
        """
        assert isinstance(templatename, str)
        assert isinstance(theversion, unicode)
        assert isinstance(thecontent, unicode)
        params= dict(
            content=thecontent, ## Note: must use the provided content, as it has to fit with the version
            version=theversion,
            ok=ok,
            error=error)
        params.update(extraparams)
        return self.render(templatename, rs, params)

    def render(self, templatename, rs, extraparams=dict()):
        """
        @type templatename: str
        @type rs: RequestState
        @type extraparams: dict
        """
        assert isinstance(templatename, str)
        rs.response.content_type = "text/html; charset=utf8"
        params = dict(
            user = rs.user,
            buildurl=lambda name, kwargs=dict(): self.buildurl(rs, name, kwargs),
            basejoin = lambda tail: urllib.basejoin(rs.request.url_root, tail)
        )
        params.update(extraparams)
        ## grab a copy of the parameters for url building
        rs.params = params
        template = self.jinjaenv.get_template(templatename)
        rs.response.data = template.render(params).encode("utf8")
        return rs.response

def main():
    userdbstore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(userdbstore)
    userdb.load()
    groupstore = storage.Storage('work', 'groupdb')
    if sys.argv[1:2] == ["forkpool"]:
        app = Application(userdb, groupstore, './df/', './templates/',
                          './style/', sessiondbpath="./work/sessiondb.sqlite3")
    else:
        app = Application(userdb, groupstore, './df/', './templates/',
                          './style/')
    app = TracebackMiddleware(app)
    staticfiles = dict(("/static/" + f, StaticFile("./static/" + f)) for f in
                       os.listdir("./static/"))
    app = SubdirMiddleware(app, staticfiles)
    if sys.argv[1:2] == ["simple"]:
        make_server("localhost", 8800, app).serve_forever()
    elif sys.argv[1:2] == ["forkpool"]:
        server = ForkpoolSCGIServer(app, 4000)
        server.enable_sighandler()
        server.run()
    else:
        server = AsynchronousSCGIServer(app, 4000)
        server.run()

if __name__ == '__main__':
    main()

