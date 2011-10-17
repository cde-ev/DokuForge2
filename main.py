#!/usr/bin/env python

import jinja2
import random
import os
import sqlite3
import copy
import re
import urllib
import werkzeug.utils
from werkzeug.wrappers import Request, Response
import werkzeug.exceptions
import werkzeug.routing
import wsgiref.util
import operator
from wsgitools.applications import StaticFile
from wsgitools.middlewares import TracebackMiddleware, SubdirMiddleware
from wsgitools.scgi.asynchronous import SCGIServer
# import other parts of Dokuforge
import academy
import course
import storage
import user

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
        @rtype: str or None
        @returns: a username or None
        """
        if self.sid is None:
            return None
        self.cur.execute("SELECT user FROM sessions WHERE sid = ?;",
                         (self.sid.decode("utf8"),))
        results = self.cur.fetchall()
        if len(results) != 1:
            return None
        return results[0][0].encode("utf8")

    def set(self, username):
        """Initiate a user session.
        @type username: str
        """
        if self.sid is None:
            self.sid = gensid()
            self.response.set_cookie(self.cookie_name, self.sid)
        self.cur.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?);",
                         (self.sid.decode("utf8"), username.decode("utf8")))
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
    def __init__(self, request, sessiondb, userdb):
        self.request = request
        self.response = Response()
        self.sessionhandler = SessionHandler(sessiondb, request, self.response)
        self.userdb = userdb
        self.user = copy.deepcopy(self.userdb.db.get(self.sessionhandler.get()))
        self.request_uri = wsgiref.util.request_uri(request.environ)
        self.application_uri = wsgiref.util.application_uri(request.environ)
        if not self.application_uri.endswith("/"):
            self.application_uri += "/"

    def login(self, username):
        self.user = copy.deepcopy(self.userdb.db[username])
        self.sessionhandler.set(self.user.name)

    def logout(self):
        self.user = None
        self.sessionhandler.delete()

    def emit_content(self, content):
        self.response.data = content
        return self.response

    def emit_template(self, template, extraparams=dict()):
        self.response.content_type = "text/html; charset=utf8"
        params = dict(
            user=self.user,
            basejoin = lambda tail: urllib.basejoin(self.application_uri, tail)
        )
        params.update(extraparams)
        return self.emit_content(template.render(params).encode("utf8"))

    def emit_permredirect(self, location):
        return werkzeug.utils.redirect(
            urllib.basejoin(self.application_uri, location), 301)

    def emit_tempredirect(self, location):
        return werkzeug.utils.redirect(
            urllib.basejoin(self.application_uri, location), 307)

class TemporaryRequestRedirect(werkzeug.exceptions.HTTPException,
                               werkzeug.routing.RoutingException):
    code = 307

    def __init__(self, new_url):
        werkzeug.routing.RoutingException.__init__(self, new_url)
        self.new_url = new_url

    def get_response(self, environ):
        return werkzeug.utils.redirect(self.new_url, self.code)


class Application:
    def __init__(self, userdb, acapath):
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader("./templates"))
        self.sessiondb = sqlite3.connect(":memory:")
        cur = self.sessiondb.cursor()
        cur.execute(SessionHandler.create_table)
        self.sessiondb.commit()
        self.userdb = userdb
        self.acapath = acapath
        self.routingmap = werkzeug.routing.Map([
            werkzeug.routing.Rule("/", methods=("GET", "HEAD"),
                                  endpoint=self.do_start),
            werkzeug.routing.Rule("/!login", methods=("POST",),
                                  endpoint=self.do_login),
            werkzeug.routing.Rule("/!logout", methods=("POST",),
                                  endpoint=self.do_logout),
            werkzeug.routing.Rule("/", methods=("GET", "HEAD"),
                                  endpoint=self.do_index),
            werkzeug.routing.Rule("/!admin", methods=("GET", "HEAD"),
                                  endpoint=self.do_admin),
            werkzeug.routing.Rule("/!admin", methods=("POST",),
                                  endpoint=self.do_adminsave),
            werkzeug.routing.Rule("/<academy>/", methods=("GET", "HEAD"),
                                  endpoint=self.do_academy),
            werkzeug.routing.Rule("/<academy>/<course>/",
                                  methods=("GET", "HEAD"),
                                  endpoint=self.do_course),
            werkzeug.routing.Rule("/<academy>/<course>/!createpage",
                                  methods=("POST",),
                                  endpoint=self.do_createpage),
            werkzeug.routing.Rule("/<academy>/<course>/!deadpages",
                                  methods=("GET", "HEAD"),
                                  endpoint=self.do_showdeadpages),
            werkzeug.routing.Rule("/<academy>/<course>/!moveup",
                                  methods=("POST",), endpoint=self.do_moveup),
            werkzeug.routing.Rule("/<academy>/<course>/!relink",
                                  methods=("POST",), endpoint=self.do_relink),
            werkzeug.routing.Rule("/<academy>/<course>/<int:page>/",
                                  methods=("GET", "HEAD"),
                                  endpoint=self.do_page),
            werkzeug.routing.Rule("/<academy>/<course>/<int:page>/!edit",
                                  methods=("GET", "HEAD"),
                                  endpoint=self.do_edit),
            werkzeug.routing.Rule("/<academy>/<course>/<int:page>/!save",
                                  methods=("POST",), endpoint=self.do_save),
            werkzeug.routing.Rule("/<academy>/<course>/<int:page>/!delete",
                                  methods=("POST",), endpoint=self.do_delete),
        ])

    def getAcademy(self, name, user=None):
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            raise werkzeug.exceptions.NotFound()
        if not os.path.isdir(os.path.join(self.acapath, name)):
            raise werkzeug.exceptions.NotFound()
        aca = academy.Academy(os.path.join(self.acapath, name))
        if user is not None and not user.allowedRead(aca):
            raise werkzeug.exceptions.Forbidden()
        return aca

    def getCourse(self, aca, coursename, user=None):
        c = aca.getCourse(coursename) # checks name
        if c is None:
            raise werkzeug.exceptions.NotFound()
        if user is not None and not user.allowedRead(aca, c):
            raise werkzeug.exceptions.Forbidden()
        return c

    def createAcademy(self, name, title, groups):
        if re.match('^[-a-zA-Z0-9]{1,200}$', name) is None:
            return False
        path = os.path.join(self.acapath, name)
        if os.path.exists(path):
            return False
        os.makedirs(path)
        aca = academy.Academy(path)
        aca.settitle(title)
        aca.setgroups(groups)
        return aca

    def listAcademies(self):
        ret = map(self.getAcademy, os.listdir(self.acapath))
        ret.sort(key=operator.attrgetter('name'))
        return ret

    @Request.application
    def __call__(self, request):
        rs = RequestState(request, self.sessiondb, self.userdb)
        try:
            endpoint, args = \
                    self.routingmap.bind_to_environ(request.environ).match()
            return endpoint(rs, **args)
        except werkzeug.routing.HTTPException, e:
            return e

    def check_login(self, rs):
        if rs.user is None:
            raise TemporaryRequestRedirect(rs.application_uri)

    def do_start(self, rs):
        if rs.user is None:
            return self.render_start(rs)
        return self.render_index(rs)

    def do_login(self, rs):
        rs.response.headers.content_type = "text/plain"
        try:
            username = rs.request.form["username"]
            password = rs.request.form["password"]
            rs.request.form["submit"] # just check for existence
        except KeyError:
            return rs.emit_content("missing form fields")
        if not self.userdb.checkLogin(username, password):
            return rs.emit_content("wrong password")
        rs.login(username)
        return self.render_index(rs)

    def do_logout(self, rs):
        rs.logout()
        return self.render_start(rs)

    def do_index(self, rs):
        self.check_login(rs)
        return self.render_index(rs)

    def do_academy(self, rs, academy = None):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        return self.render_academy(rs, aca)

    def do_course(self, rs, academy = None, course = None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
        return self.render_course(rs, aca, c)

    def do_showdeadpages(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_deadpages(rs, aca, c)

    def do_createpage(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.newpage(user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_delete(self, rs, academy=None, course=None, page=None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.delpage(page, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_relink(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        numberstr = rs.request.form["number"]
        try:
            number = int(numberstr)
        except ValueError:
            number = 0
        c.relink(number, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_moveup(self, rs, academy=None, course=None):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
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
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
        return self.render_show(rs, aca, c, page)

    def do_edit(self, rs, academy = None, course = None, page = None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        version, content = c.editpage(page)
        return self.render_edit(rs, aca, c, page, version, content)

    def do_save(self, rs, academy = None, course = None, page = None):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy.encode("utf8"), rs.user)
        c = self.getCourse(aca, course.encode("utf8"), rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()

        userversion = rs.request.form["revisionstartedwith"]
        usercontent = rs.request.form["content"]

        ok, version, content = c.savepage(page, userversion, usercontent)

        issaveshow = "saveshow" in rs.request.form
        if ok and issaveshow:
            return self.render_show(rs, aca, c, page, saved=True)

        return self.render_edit(rs, aca, c, page, version, content, ok=ok)

    def do_admin(self, rs):
        self.check_login(rs)
        if not rs.user.isAdmin():
            return werkzeug.exceptions.Forbidden()
        version, content = self.userdb.storage.startedit()
        return self.render_admin(rs, version, content)

    def do_adminsave(self, rs):
        self.check_login(rs)
        if not rs.user.isAdmin():
            return werkzeug.exceptions.Forbidden()
        userversion = rs.request.form["revisionstartedwith"]
        usercontent = rs.request.form["content"]
        ok, version, content = self.userdb.storage.endedit(userversion, usercontent, user=rs.user.name)
        self.userdb.load()
        return self.render_admin(rs, version, content, ok=ok)

    def render_start(self, rs):
        return rs.emit_template(self.jinjaenv.get_template("start.html"))

    def render_edit(self, rs, theacademy, thecourse, thepage, theversion, thecontent, ok=None):
        params= dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            content=thecontent, ## Note: must use the provided content, as it has to fit with the version
            version=theversion,
            ok=ok)
        return rs.emit_template(self.jinjaenv.get_template("edit.html"),params)


    def render_index(self, rs):
        params = dict(
            academies=map(academy.AcademyLite, self.listAcademies()))
        return rs.emit_template(self.jinjaenv.get_template("index.html"),
                                params)

    def render_academy(self, rs, theacademy):
        return rs.emit_template(self.jinjaenv.get_template("academy.html"),
                                dict(academy=academy.AcademyLite(theacademy)))

    def render_deadpages(self, rs, theacademy, thecourse):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse))
        return rs.emit_template(self.jinjaenv.get_template("dead.html"),
                                params)

    def render_course(self, rs, theacademy, thecourse):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse))
        return rs.emit_template(self.jinjaenv.get_template("course.html"),
                                params)

    def render_show(self, rs, theacademy, thecourse,thepage, saved=False):
        params = dict(
            academy=academy.AcademyLite(theacademy),
            course=course.CourseLite(thecourse),
            page=thepage,
            content=thecourse.showpage(thepage),
            saved=saved)
        return rs.emit_template(self.jinjaenv.get_template("show.html"),
                                params)

    def render_admin(self, rs, theversion, thecontent, ok=None):
        params= dict(
            content=thecontent, ## Note: must use the provided content, as it has to fit with the version
            version=theversion,
            ok=ok)
        return rs.emit_template(self.jinjaenv.get_template("admin.html"),params)


def main():
    userdbstore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(userdbstore)
    userdb.load()
    app = Application(userdb, './df/')
    app = TracebackMiddleware(app)
    staticfiles = dict(("/static/" + f, StaticFile("./static/" + f)) for f in
                       os.listdir("./static/"))
    app = SubdirMiddleware(app, staticfiles)
    server = SCGIServer(app, 4000)
    server.run()

if __name__ == '__main__':
    main()

