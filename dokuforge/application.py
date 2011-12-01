#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ConfigParser
import copy
from cStringIO import StringIO
try:
    from hashlib import md5 as getmd5
except ImportError:
    from md5 import new as getmd5
import operator
import os
import random
import sqlite3
import time
import urllib
import urlparse

import jinja2
import werkzeug.exceptions
import werkzeug.routing
import werkzeug.utils
from werkzeug.wrappers import Request, Response

from dokuforge.academy import Academy
import dokuforge.common as common
from dokuforge.common import CheckError
from dokuforge.parser import Parser
from dokuforge.htmlformatter import HtmlFormatter
try:
    from dokuforge.versioninfo import commitid
except ImportError:
    commitid = "unknown"

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
                   "(sid TEXT, user TEXT, updated INTEGER, UNIQUE(sid));"
    cookie_name = "sid"
    hit_interval = 60
    expire_after = 60 * 60 * 24 * 7 # a week

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
        self.lastexpire = 0

    def get(self):
        """Find a user session.
        @rtype: unicode or None
        @returns: a username or None
        """
        now = time.time()
        self.expire(now)

        if self.sid is None:
            return None
        self.cur.execute("SELECT user, updated FROM sessions WHERE sid = ?;",
                         (self.sid.decode("utf8"),))
        results = self.cur.fetchall()
        if len(results) != 1:
            return None
        assert isinstance(results[0][0], unicode)
        if results[0][1] + self.hit_interval < time.time():
            self.cur.execute("UPDATE sessions SET updated = ? WHERE sid = ?;",
                             (now, self.sid.decode("utf8")))
            self.db.commit()
        return results[0][0]

    def set(self, username):
        """Initiate a user session.
        @type username: unicode
        """
        if self.sid is None:
            self.sid = gensid()
            self.response.set_cookie(self.cookie_name, self.sid)
        self.cur.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?);",
                         (self.sid.decode("utf8"), username, time.time()))
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

    def expire(self, now=None):
        """Delete old cookies unless there was active expire call within the
        last hit_interval seconds.
        @type now: None or float
        @param now: time.time() result if already present
        """
        if now is None:
            now = time.time()
        if self.lastexpire + self.hit_interval < now:
            self.cur.execute("DELETE FROM sessions WHERE updated < ?;",
                             (time.time() - self.expire_after,))
            self.db.commit()
            self.lastexpire = now

class RequestState:
    """
    @type endpoint_args: {str: object}
    @ivar endpoint_args: is a reference to the parameters obtained from
        werkzeug's url matcher
    """
    def __init__(self, request, sessiondb, userdb, mapadapter):
        self.request = request
        self.response = Response()
        self.sessionhandler = SessionHandler(sessiondb, request, self.response)
        self.userdb = userdb
        self.user = copy.deepcopy(self.userdb.db.get(self.sessionhandler.get()))
        self.mapadapter = mapadapter
        self.endpoint_args = None # set later in Application.render

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

class IdentifierConverter(werkzeug.routing.BaseConverter):
    regex = '[a-zA-Z][-a-zA-Z0-9]{0,199}'

class Application:
    def __init__(self, pathconfig):
        """
        @type pathconfig: PathConfig
        """
        self.sessiondb = sqlite3.connect(pathconfig.sessiondbpath)
        cur = self.sessiondb.cursor()
        cur.execute(SessionHandler.create_table)
        self.sessiondb.commit()
        self.userdb = pathconfig.loaduserdb()
        self.acapath = pathconfig.dfdir
        self.templatepath = os.path.join(os.path.dirname(__file__), "templates")
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader(self.templatepath))
        self.groupstore = pathconfig.groupstore
        self.staticservepath = pathconfig.staticservepath
        self.mathjaxuri = pathconfig.mathjaxuri
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
            rule("/docs/<identifier:academy>/<identifier:course>/<int:page>/!uploadblob",
                 methods=("POST",), endpoint="uploadblob"),
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

    def buildurl(self, rs, endpoint, args):
        """Looks up up the given endpoint in the routingmap and builds the
        corresponding url with the passed args. Missing args are added if the
        given endpoint requests them and they are present in the request uri as
        parsed by werkzeug's routing and stored in rs.endpoint_args.

        @type rs: RequestState
        @type endpoint: str
        @param endpoint: an endpoint from self.routingmap
        @type args: {str: object}
        @param args: a mapping from rule parameters to their values
        @rtype: str
        """
        assert isinstance(endpoint, str)
        buildargs = dict()
        for key, value in rs.endpoint_args.items():
            if self.routingmap.is_endpoint_expecting(endpoint, key):
                buildargs[key] = value
        buildargs.update(args)
        return rs.mapadapter.build(endpoint, buildargs)

    def staticjoin(self, name, rs):
        """
        @type rs: RequestState
        @type name: str
        @param name: filename to serve statically
        @returns: url for the file
        """
        assert isinstance(name, str)
        ## If staticservepath is a full url, the join is the staticservepath.
        static = urlparse.urljoin(rs.request.url_root, self.staticservepath)
        return urlparse.urljoin(static, name)

    def mathjaxjoin(self, name, rs):
        """
        @type rs: RequestState
        @type name: str
        @param name: filename to serve from mathjax
        @returns: url for the file
        """
        assert isinstance(name, str)
        ## If mathjaxuri is a full url, the join is the mathjaxuri.
        mathjax = urlparse.urljoin(rs.request.url_root, self.mathjaxuri)
        return urlparse.urljoin(mathjax, name)

    def getAcademy(self, name, user=None):
        """
        look up an academy for a given name. If none is found raise a
        werkzeug.exceptions.NotFound.

        @type name: unicode
        @type user: None or User
        @rtype: Academy
        @raises werkzeug.exceptions.HTTPException:
        """
        assert isinstance(name, unicode)
        name = name.encode("utf8")
        try:
            common.validateInternalName(name)
            common.validateExistence(self.acapath, name)
        except CheckError:
            raise werkzeug.exceptions.NotFound()
        aca = Academy(os.path.join(self.acapath, name), self.listGroups)
        if user is not None and not user.allowedRead(aca):
            raise werkzeug.exceptions.Forbidden()
        return aca

    def getCourse(self, aca, coursename, user=None):
        """
        @type aca: Academy
        @type coursename: unicode
        @type user: None or User
        @rtype: Course
        @raises werkzeug.exceptions.HTTPException:
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
        create an academy. If the user data is malformed raise a CheckError.

        @type name: unicode
        @type title: unicode
        @rtype: None or Academy
        @raises CheckError:
        """
        assert isinstance(name, unicode)
        assert isinstance(title, unicode)
        assert all(isinstance(group, unicode) for group in groups)
        name = name.encode("utf8")
        common.validateInternalName(name)
        common.validateNonExistence(self.acapath, name)
        common.validateTitle(title)
        common.validateGroups(groups, self.listGroups())
        path = os.path.join(self.acapath, name)
        os.makedirs(path)
        aca = Academy(path, self.listGroups)
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
        """
        @rtype: {unicode: unicode}
        @returns: a dict of all groups with their titles as values
        """
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
        self.userdb.load()
        rs = RequestState(request, self.sessiondb, self.userdb, mapadapter)
        try:
            endpoint, args = mapadapter.match()
            ## grab a copy of the parameters for url building
            rs.endpoint_args = args
            return getattr(self, "do_%s" % endpoint)(rs, **args)
        except werkzeug.routing.HTTPException, e:
            return e

    def check_login(self, rs):
        """
        @type rs: RequestState
        @raises TemporaryRequestRedirect: unless the user is logged in
        """
        if rs.user is None:
            raise TemporaryRequestRedirect(rs.request.url_root)

    def do_file(self, rs, filestore, template, extraparams=dict()):
        """
        Function to generically handle editing a single file.

        @type rs: RequestState
        @type filestore: Storage
        @type template: str
        @type extraparams: dict
        @param filestore: the file which should be edited
        @param template: the template with which to render the edit mask
        @param extraparams: any further params the template needs
        """
        assert isinstance(template, str)
        version, content = filestore.startedit()
        return self.render_file(rs, template, version.decode("utf8"),
                                content.decode("utf8"), extraparams=extraparams)

    def do_filesave(self, rs, filestore, template, checkhook=None,
                    savehook=None, extraparams=dict()):
        """
        Function to generically handle saving a single file.

        @type rs: RequestState
        @type filestore: Storage
        @type template: str
        @type checkhook: None or callable
        @type savehook: None or callable
        @type extraparams: dict
        @param filestore: the file which should be edited
        @param template: the template with which to render the edit mask
        @param checkhook: function to call before saving the content. The
            function may raise a CheckError if an anomaly is encountered, the
            error is then displayed, the content is not saved, but offered for
            further edits.
        @param savehook: function to call after saving the content.
        @param extraparams: any further params the template needs
        """
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
        if not ok:
            error = CheckError(u"Es ist ein Konflikt mit einer anderen Änderung aufgetreten!",
                               u"Bitte löse den Konflikt auf und speichere danach erneut.")
            return self.render_file(rs, template, version, content, ok=False,
                                    error = error, extraparams=extraparams)
        if not savehook is None:
            savehook()
        return self.render_file(rs, template, version, content, ok=True,
                                extraparams=extraparams)

    def do_property(self, rs, getter, template, extraparams=dict()):
        """
        Function to generically handle editing a single property. The showy
        part.

        @type rs: RequestState
        @type getter: callale
        @type template: str
        @type extraparams: dict
        @param getter: getter function for the property to edit
        @param template: the template with which to render the edit mask
        @param extraparams: any further params the template needs
        """
        assert isinstance(template, str)
        content = getter()
        assert isinstance(content, unicode)
        return self.render_property(rs, template, content,
                                    extraparams=extraparams)

    def do_propertysave(self, rs, setter, template, extraparams=dict()):
        """
        Function to generically handle editing a single property. The worker
        part.

        @type rs: RequestState
        @type setter: callable
        @type template: str
        @type extraparams: dict
        @param setter: setter function for the property to edit
        @param template: the template with which to render the edit mask
        @param extraparams: any further params the template needs
        """
        usercontent = rs.request.form["content"]
        try:
            setter(usercontent)
        except CheckError as err:
            return self.render_property(rs, template, usercontent,
                                        ok=False, error = err,
                                        extraparams=extraparams)
        return self.render_property(rs, template, usercontent, ok=True,
                                    extraparams=extraparams)

    ## here come the endpoint handler

    def do_start(self, rs):
        """
        @type rs: RequestState
        """
        if rs.user is None:
            return self.render_start(rs)
        return self.render_index(rs)

    def do_login(self, rs):
        """
        @type rs: RequestState
        """
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
        """
        @type rs: RequestState
        """
        rs.logout()
        return self.render_start(rs)

    def do_index(self, rs):
        """
        @type rs: RequestState
        """
        self.check_login(rs)
        return self.render_index(rs, None)

    def do_groupindex(self, rs, group=None):
        """
        @type rs: RequestState
        @type group: None or unicode
        """
        self.check_login(rs)
        return self.render_index(rs, group)

    def do_academy(self, rs, academy = None):
        """
        @type rs: RequestState
        @type academy: unicode
        """
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        return self.render_academy(rs, aca)

    def do_course(self, rs, academy = None, course = None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        """
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        return self.render_course(rs, aca, c)

    def do_showdeadpages(self, rs, academy=None, course=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        """
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_deadpages(rs, aca, c)

    def do_showdeadblobs(self, rs, academy=None, course=None, page=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_deadblobs(rs, aca, c, page)

    def do_createcoursequiz(self, rs, academy=None):
        """
        @type rs: RequestState
        @type academy: unicode
        """
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.render_createcoursequiz(rs, aca)

    def do_createcourse(self, rs, academy=None):
        """
        @type rs: RequestState
        @type academy: unicode
        """
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        name = rs.request.form["name"] # FIXME: raises KeyError
        title = rs.request.form["title"] # FIXME: raises KeyError
        try:
            aca.createCourse(name, title)
        except CheckError as error:
            return self.render_createcoursequiz(rs, aca, ok=False,
                                                error = error)
        return self.render_academy(rs, aca)

    def do_createacademyquiz(self, rs):
        """
        @type rs: RequestState
        """
        self.check_login(rs)
        if not rs.user.mayCreate():
            return werkzeug.exceptions.Forbidden()
        return self.render_createacademyquiz(rs)

    def do_createacademy(self, rs):
        """
        @type rs: RequestState
        """
        self.check_login(rs)
        if not rs.user.mayCreate():
            return werkzeug.exceptions.Forbidden()
        name = rs.request.form["name"] # FIXME: raises KeyError
        title = rs.request.form["title"] # FIXME: raises KeyError
        groups = rs.request.form.getlist("groups") # FIXME: raises KeyError
        try:
            self.createAcademy(name, title, groups)
        except CheckError as error:
            return self.render_createacademyquiz(rs, ok=False, error = error)
        return self.render_index(rs)

    def do_styleguide(self, rs):
        """
        @type rs: RequestState
        """
        return self.do_styleguidetopic(rs, u"index")

    def do_styleguidetopic(self, rs, topic=None):
        """
        @type rs: RequestState
        @type topic: unicode
        """
        assert isinstance(topic, unicode)
        topic = topic.encode("utf8")
        if not topic in os.listdir(os.path.join(self.templatepath,
                                                "style")):
            raise werkzeug.exceptions.NotFound()
        return self.render_styleguide(rs, topic)

    def do_createpage(self, rs, academy=None, course=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        """
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.newpage(user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_delete(self, rs, academy=None, course=None, page=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.delpage(page, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_blobdelete(self, rs, academy=None, course=None, page=None,
                      blob=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        @type blob: int
        """
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.delblob(blob, user=rs.user.name)
        return self.render_show(rs, aca, c, page)

    def do_relink(self, rs, academy=None, course=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        """
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        numberstr = rs.request.form["number"] # FIXME: raises KeyError
        try:
            number = int(numberstr)
        except ValueError:
            number = 0
        c.relink(number, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_relinkblob(self, rs, academy=None, course=None, page=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        numberstr = rs.request.form["number"] # FIXME: raises KeyError
        try:
            number = int(numberstr)
        except ValueError:
            number = 0
        c.relinkblob(number, page, user=rs.user.name)
        return self.render_show(rs, aca, c, page)

    def do_showblob(self, rs, academy=None, course=None, page=None, blob=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        @type blob: int
        """
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_showblob(rs, aca, c, page, blob)

    def do_editblob(self, rs, academy=None, course=None, page=None, blob=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        @type blob: int
        """
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_editblob(rs, aca, c, page, blob)


    def do_saveblob(self, rs, academy=None, course=None, page=None, blob=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        @type blob: int
        """
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()

        newlabel = rs.request.form["label"] # FIXME: raises KeyError
        newcomment = rs.request.form["comment"] # FIXME: raises KeyError
        newname = rs.request.form["name"] # FIXME: raises KeyError

        try:
            c.modifyblob(blob, newlabel, newcomment, newname, rs.user.name)
        except CheckError as error:
            return self.render_editblob(rs, aca, c, page, blob, ok=False,
                                        error=error)
        return self.render_showblob(rs, aca, c, page, blob)


    def do_md5blob(self, rs, academy=None, course=None, page=None, blob=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        @type blob: int
        """
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        h = getmd5()
        theblob = c.viewblob(blob)
        h.update(theblob["data"])
        blobhash = h.hexdigest()
        return self.render_showblob(rs, aca, c, page, blob, blobhash=blobhash)

    def do_downloadblob(self, rs, academy=None, course=None, page=None,
                        blob=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        @type blob: int
        """
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/octet-stream"
        theblob = c.viewblob(blob)
        rs.response.data = theblob["data"]
        rs.response.headers['Content-Disposition'] = \
                "attachment; filename=%s" % theblob["filename"]
        return rs.response

    def do_rcs(self, rs, academy=None, course=None, page=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/octet-stream"
        rs.response.data = c.getrcs(page)
        rs.response.headers['Content-Disposition'] = \
                "attachment; filename=%d,v" % (page)
        return rs.response

    def do_raw(self, rs, academy=None, course=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        """
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/x-bzip-compressed-tar"
        rs.response.data = c.export()
        rs.response.headers['Content-Disposition'] = \
                "attachment; filename=%s_%s.tar.bz2" % (aca.name, c.name)
        return rs.response

    def do_moveup(self, rs, academy=None, course=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        """
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        numberstr = rs.request.form["number"] # FIXME: raises KeyError
        try:
            number = int(numberstr)
        except ValueError:
            number = 0
        c.swappages(number, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_page(self, rs, academy = None, course = None, page = None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        return self.render_show(rs, aca, c, page)

    def do_edit(self, rs, academy = None, course = None, page = None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        version, content = c.editpage(page)
        return self.render_edit(rs, aca, c, page, version, content)

    def do_addblob(self, rs, academy = None, course = None, page = None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_addblob(rs, aca, c, page)

    def do_uploadblob(self, rs, academy = None, course = None, page = None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()

        usercomment = rs.request.form["comment"]
        userlabel = rs.request.form["label"]

        try:
            common.validateBlobLabel(userlabel)
            common.validateBlobComment(usercomment)
        except CheckError as error:
            return self.render_addblob(rs, aca, c, page,  ok=False,
                                       error=error)
        return self.render_uploadblob(rs, aca, c, page)

    def do_attachblob(self, rs, academy = None, course = None, page = None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()

        usercomment = rs.request.form["comment"] # FIXME: raises KeyError
        userlabel = rs.request.form["label"] # FIXME: raises KeyError
        # a FileStorage is sufficiently file-like for store
        usercontent = rs.request.files["content"] # FIXME: raises KeyError

        ## This is a bit tedious since we don't want to drop the blob and
        ## force the user to retransmit it.
        try:
            c.attachblob(page, usercontent, comment=usercomment,
                         label=userlabel, user=rs.user.name)
        except common.InvalidBlobFilename as error:
            usercontent.filename = common.sanitizeBlobFilename(
                usercontent.filename)
            try:
                blob = c.attachblob(page, usercontent, comment=usercomment,
                                label=userlabel, user=rs.user.name)
            except CheckError:
                ## this case should never happen
                ## (except manually crafted POSTs)
                return self.render_addblob(rs, aca, c, page)
            else:
                return self.render_editblob(rs, aca, c, page, blob, ok=False,
                                            error=error)
        except CheckError:
            return self.render_addblob(rs, aca, c, page) # also shouldn't happen
        else:
            return self.render_show(rs, aca, c, page)

    def do_save(self, rs, academy = None, course = None, page = None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        @type page: int
        """
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()

        userversion = rs.request.form["revisionstartedwith"] # FIXME: raises KeyError
        usercontent = rs.request.form["content"] # FIXME: raises KeyError

        ok, version, content = c.savepage(page, userversion, usercontent,
                                          user=rs.user.name)

        issaveshow = "saveshow" in rs.request.form
        if ok and issaveshow:
            return self.render_show(rs, aca, c, page, saved=True)

        return self.render_edit(rs, aca, c, page, version, content, ok=ok)

    def do_academygroups(self, rs, academy=None):
        """
        @type rs: RequestState
        @type academy: unicode
        """
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.render_academygroups(rs, aca)

    def do_academygroupssave(self, rs, academy=None):
        """
        @type rs: RequestState
        @type academy: unicode
        """
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        groups = rs.request.form.getlist("groups") # FIXME: raises KeyError
        try:
            aca.setgroups(groups)
        except CheckError as error:
            return self.render_academygroups(rs, aca,  ok = False,
                                             error = error)
        return self.render_academygroups(rs, aca, ok = True)

    def do_academytitle(self, rs, academy=None):
        """
        @type rs: RequestState
        @type academy: unicode
        """
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_property(rs, aca.gettitle,
                                "academytitle.html",
                                extraparams={'academy': aca.view()})

    def do_academytitlesave(self, rs, academy=None):
        """
        @type rs: RequestState
        @type academy: unicode
        """
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedWrite(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_propertysave(rs, aca.settitle,
                                    "academytitle.html",
                                    extraparams = {'academy': aca.view()})

    def do_coursetitle(self, rs, academy=None, course=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        """
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.do_property(rs, c.gettitle,
                                "coursetitle.html",
                                extraparams={'academy': aca.view(),
                                             'course': c.view()})

    def do_coursetitlesave(self, rs, academy=None, course=None):
        """
        @type rs: RequestState
        @type academy: unicode
        @type course: unicode
        """
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.do_propertysave(rs, c.settitle,
                                    "coursetitle.html",
                                    extraparams={'academy': aca.view(),
                                                 'course': c.view()})

    def do_admin(self, rs):
        """
        @type rs: RequestState
        """
        self.check_login(rs)
        if not rs.user.isAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, self.userdb.storage, "admin.html")

    def do_adminsave(self, rs):
        """
        @type rs: RequestState
        """
        self.check_login(rs)
        if not rs.user.isAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, self.userdb.storage, "admin.html",
                                checkhook = common.validateUserConfig,
                                savehook = self.userdb.load)

    def do_groups(self, rs):
        """
        @type rs: RequestState
        """
        self.check_login(rs)
        if not rs.user.isSuperAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, self.groupstore, "groups.html")

    def do_groupssave(self, rs):
        """
        @type rs: RequestState
        """
        self.check_login(rs)
        if not rs.user.isSuperAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, self.groupstore, "groups.html",
                                checkhook = common.validateGroupConfig)

    ### here come the renderer

    def render_start(self, rs):
        """
        @type rs: RequestState
        """
        return self.render("start.html", rs)

    def render_styleguide(self, rs, topic):
        """
        @type rs: RequestState
        @type topic: unicode
        """
        params = dict(
            topic = topic,
            includepath = os.path.join("style", topic)
            )
        return self.render("style.html", rs, params)

    def render_edit(self, rs, theacademy, thecourse, thepage, theversion,
                    thecontent, ok=None):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        @type thepage: int
        @type theversion: unicode
        @type thecontent: unicode
        @type ok: None or bool
        """
        assert isinstance(theversion, unicode)
        assert isinstance(thecontent, unicode)
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            ## Note: must use the provided content, as it has to fit with the
            ## version
            content=thecontent,
            version=theversion,
            ok=ok,
            allowMathChange = False)
        return self.render("edit.html", rs, params)


    def render_index(self, rs, group = None):
        """
        @type rs: RequestState
        @type group: None or unicode
        """
        if group is None:
            group = rs.user.defaultGroup()
        params = dict(
            academies=[academy.view() for academy in self.listAcademies()],
            allgroups=self.listGroups(),
            group=group)
        return self.render("index.html", rs, params)

    def render_academy(self, rs, theacademy):
        """
        @type rs: RequestState
        @type theacademy: Academy
        """
        return self.render("academy.html", rs,
                           dict(academy=theacademy.view()))

    def render_deadblobs(self, rs, theacademy, thecourse, thepage):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        @type thepage: int
        """
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            blobs=[thecourse.viewblob(i) for i in thecourse.listdeadblobs()])
        return self.render("deadblobs.html", rs, params)

    def render_deadpages(self, rs, theacademy, thecourse):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        """
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view())
        return self.render("dead.html", rs, params)

    def render_course(self, rs, theacademy, thecourse):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        """
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view())
        return self.render("course.html", rs, params)

    def render_addblob(self, rs, theacademy, thecourse, thepage, ok=None,
                       error=None):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        @type thepage: int
        """
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            ok=ok,
            error=error,
            allowMathChange = False)
        return self.render("addblob.html", rs, params)


    def render_uploadblob(self, rs, theacademy, thecourse, thepage):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        @type thepage: int
        """
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            allowMathChange = False)
        return self.render("uploadblob.html", rs, params)

    def render_showblob(self, rs, theacademy, thecourse, thepage, blob,
                        blobhash=None):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        @type thepage: int
        @type blob: int
        @type blobhash: None or str
        """
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            blob=thecourse.viewblob(blob),
            blobhash=blobhash)
        return self.render("showblob.html", rs, params)

    def render_editblob(self, rs, theacademy, thecourse, thepage, blob, ok=None,
                        error=None):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        @type thepage: int
        @type blob: int
        @type ok: None or bool
        @type error: None or CheckError
        """
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            blob=thecourse.viewblob(blob),
            ok=ok,
            error=error,
            allowMathChange = False)
        return self.render("editblob.html", rs, params)


    def render_createcoursequiz(self, rs, theacademy, ok=None, error=None):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type ok: None or Boolean
        @type error: None or CheckError
        """
        params = dict(academy=theacademy.view(),
                      ok=ok,
                      error=error,
                      allowMathChange = False)
        return self.render("createcoursequiz.html", rs, params)

    def render_createacademyquiz(self, rs, ok=None, error=None):
        """
        @type rs: RequestState
        @type ok: None or Boolean
        @type error: None or CheckError
        """
        params = dict(ok=ok,
                      error=error,
                      allgroups=self.listGroups(),
                      allowMathChange = False)
        return self.render("createacademyquiz.html", rs, params)

    def render_academygroups(self, rs, theacademy, ok = None, error = None):
        """
        @type rs: RequestState
        @type theacademy: Academy
        """
        params = dict(academy = theacademy.view(),
                      allgroups = self.listGroups(),
                      allowMathChange = False,
                      ok = ok,
                      error = error)
        return self.render("academygroups.html", rs, params)

    def render_show(self, rs, theacademy, thecourse, thepage, saved=False):
        """
        @type rs: RequestState
        @type theacademy: Academy
        @type thecourse: Course
        @type thepage: int
        @type saved: bool
        """
        parser = Parser(thecourse.showpage(thepage))
        tree = parser.parse()
        html = HtmlFormatter(tree)
        estimate = thecourse.estimatepage(thepage, tree)
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            commit = thecourse.getcommit(thepage),
            content=html.generateoutput(),
            estimate=estimate,
            saved=saved,
            blobs=[thecourse.viewblob(i) for i in thecourse.listblobs(thepage)])
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
        params = dict(
            ## Note: must use the provided content, as it has to fit with the
            ## version
            content=thecontent,
            version=theversion,
            ok=ok,
            error=error,
            allowMathChange = False)
        params.update(extraparams)
        return self.render(templatename, rs, params)

    def render_property(self, rs, templatename, thecontent, ok=None,
                        error=None, extraparams=dict()):
        """
        @type rs: RequestState
        @type templatename: str
        @type thecontent: unicode
        @type ok: None or Booleon
        @type error: None or CheckError
        @type extraparams: dict
        """
        assert isinstance(templatename, str)
        assert isinstance(thecontent, unicode)
        params = dict(
            content=thecontent,
            ok=ok,
            error=error,
            allowMathChange = False)
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
        allowMathChange = True
        if rs.request.method == "POST":
            allowMathChange = False
        params = dict(
            user = rs.user,
            commitid=commitid.decode("utf8"),
            form=rs.request.form,
            buildurl=lambda name, kwargs=dict(): self.buildurl(rs, name, kwargs),
            basejoin = lambda tail: urllib.basejoin(rs.request.url_root, tail),
            staticjoin = lambda name: self.staticjoin(name, rs),
            mathjaxjoin = lambda name: self.mathjaxjoin(name, rs),
            allowMathChange = allowMathChange)
        params.update(extraparams)
        template = self.jinjaenv.get_template(templatename)
        rs.response.data = template.render(params).encode("utf8")
        return rs.response
