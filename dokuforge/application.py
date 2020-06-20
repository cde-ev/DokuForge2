#!/usr/bin/env python
# -*- coding: utf-8 -*-

import configparser
import copy
import datetime
from hashlib import md5 as getmd5
import logging
import operator
import os
import random
import sqlite3
import sys
import time
import typing
import urllib
from urllib import parse as urlparse

import jinja2
import werkzeug.exceptions
import werkzeug.routing
import werkzeug.utils
from werkzeug.wrappers import Request, Response
from wsgitools.digest import LazyDBAPI2Opener

from dokuforge.academy import Academy
import dokuforge.common as common
from dokuforge.common import CheckError
from dokuforge.course import Course
from dokuforge.parser import dfLineGroupParser, Estimate
import dokuforge.paths
from dokuforge.storage import Storage
from dokuforge.user import User
try:
    from dokuforge.versioninfo import commitid
except ImportError:
    commitid = "unknown"

sysrand = random.SystemRandom()

logger = logging.getLogger(__name__)


def gensid(bits: int = 64) -> str:
    """
    @param bits: randomness in bits of the resulting string
    @returns: a random string
    """
    return "%x" % sysrand.getrandbits(bits)

class SessionHandler:
    """Associate users with session ids in a DBAPI2 database. The database
    may be optimized for performance -- that is we accept an unlikely loss
    of the session database for performance reasons since the information
    therein is ephemeral by nature and loss has little impact."""
    create_table = "CREATE TABLE IF NOT EXISTS sessions " + \
                   "(sid TEXT, user TEXT, updated INTEGER, UNIQUE(sid));"
    cookie_name = "sid"
    hit_interval = 60
    expire_after = 60 * 60 * 24 * 7 # a week

    def __init__(self, db) -> None:
        """
        @param db: a DBAPI2 database that has a sessions table as described
                in the create_table class variable
        """
        self.db = db
        self.lastexpire = 0

    def get(self, request: werkzeug.wrappers.Request) -> \
            typing.Tuple[typing.Optional[str], typing.Optional[str]]:
        """Find a user session.
        @returns: a pair (sid, username). sid is None if the cookie is missing
                and username is None if sid cannot be found in the database
        """
        now = time.time()
        self.expire(now)

        sid = request.cookies.get(self.cookie_name)

        if sid is None:
            logger.debug("SessionHandler.get: no cookie found")
            return (None, None)
        cur = self.db.cursor()
        cur.execute("SELECT user, updated FROM sessions WHERE sid = ?;", (sid,))
        results = cur.fetchall()
        if len(results) != 1:
            logger.debug("SessionHandler.get: cookie %r not found", sid)
            self.db.commit()
            cur.close()
            return (sid, None)
        username, updated = results[0]
        assert isinstance(username, str)
        if updated + self.hit_interval < now:
            cur.execute("UPDATE sessions SET updated = ? WHERE sid = ?;",
                             (now, sid))
            self.db.commit()
        logger.debug("SessionHandler.get: cookie %r matches user %r", sid,
                username)
        self.db.commit()
        cur.close()
        return (sid, username)

    def set(self, response: werkzeug.wrappers.Response, username: str,
            sid: typing.Optional[str] = None) -> str:
        """Initiate a user session.
        @returns: sid
        """
        action = "reusing"
        if sid is None:
            sid = gensid()
            response.set_cookie(self.cookie_name, sid)
            action = "generating new"
        logger.debug("SessionHandler.set: %s cookie %r for user %r", action,
                    sid, username)
        cur = self.db.cursor()
        cur.execute("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?);",
                         (sid, username, time.time()))
        self.db.commit()
        cur.close()
        return sid

    def delete(self, response: werkzeug.wrappers.Response, sid: str) -> None:
        """Delete a user session."""
        if sid is not None:
            logger.debug("SessionHandler.delete: deleting cookie %r", sid)
            cur = self.db.cursor()
            cur.execute("DELETE FROM sessions WHERE sid = ?;", (sid,))
            self.db.commit()
            cur.close()
            response.delete_cookie(self.cookie_name)
        else:
            logger.debug("SessionHandler.delete: no cookie to delete")

    def expire(self, now: typing.Optional[float] = None) -> None:
        """Delete old cookies unless there was active expire call within the
        last hit_interval seconds.
        @param now: time.time() result if already present
        """
        if now is None:
            now = time.time()
        if self.lastexpire + self.hit_interval < now:
            logger.debug("SessionHandler.expire: taking action")
            cur = self.db.cursor()
            cur.execute("DELETE FROM sessions WHERE updated < ?;",
                             (now - self.expire_after,))
            self.db.commit()
            cur.close()
            self.lastexpire = now

class RequestState:
    """
    @ivar endpoint_args: is a reference to the parameters obtained from
        werkzeug's url matcher
    """
    def __init__(self, request, sessionhandler, userdb, mapadapter) -> None:
        self.request = request
        self.response = Response()
        self.sessionhandler = sessionhandler
        self.userdb = userdb
        self.sid, username = self.sessionhandler.get(request)
        self.user = copy.deepcopy(self.userdb.db.get(username))
        self.mapadapter = mapadapter
        self.endpoint_args: typing.Dict[str, typing.Any] = None
        # set later in Application.render

    def login(self, username) -> None:
        self.user = copy.deepcopy(self.userdb.db[username])
        self.sid = self.sessionhandler.set(self.response, self.user.name,
                self.sid)

    def logout(self) -> None:
        self.user = None
        self.sessionhandler.delete(self.response, self.sid)
        self.sid = None

class TemporaryRequestRedirect(werkzeug.exceptions.HTTPException,
                               werkzeug.routing.RoutingException):
    code = 307

    def __init__(self, new_url) -> None:
        werkzeug.routing.RoutingException.__init__(self, new_url)
        self.new_url = new_url

    def get_response(self, environ):
        return werkzeug.utils.redirect(self.new_url, self.code)

class IdentifierConverter(werkzeug.routing.BaseConverter):
    regex = '[a-zA-Z][-a-zA-Z0-9]{0,199}'

class Application:
    def __init__(self, pathconfig: dokuforge.paths.PathConfig) -> None:
        self.sessiondbpath = pathconfig.sessiondbpath
        sessiondb = LazyDBAPI2Opener(self.connectdb)
        self.sessionhandler = SessionHandler(sessiondb)
        self.userdb = pathconfig.loaduserdb()
        self.acapath = pathconfig.dfdir
        self.templatepath = os.path.join(os.path.dirname(__file__), "templates")
        self.jinjaenv = jinja2.Environment(
                loader=jinja2.FileSystemLoader(self.templatepath))
        self.groupstore = pathconfig.groupstore
        self.staticservepath = pathconfig.staticservepath
        self.mathjaxuri = pathconfig.mathjaxuri
        self.staticexportdir = pathconfig.staticexportdir
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
            rule("/docs/<identifier:academy>/!export", methods=("GET", "HEAD"),
                 endpoint="export"),
            rule("/docs/<identifier:academy>/!raw", methods=("GET", "HEAD"),
                 endpoint="rawacademy"),
            rule("/docs/<identifier:academy>/!groups", methods=("GET", "HEAD"),
                 endpoint="academygroups"),
            rule("/docs/<identifier:academy>/!groups", methods=("POST",),
                 endpoint="academygroupssave"),
            rule("/docs/<identifier:academy>/!title", methods=("GET", "HEAD"),
                 endpoint="academytitle"),
            rule("/docs/<identifier:academy>/!title", methods=("POST",),
                 endpoint="academytitlesave"),
            rule("/docs/<identifier:academy>/!deadcourses", methods=("GET",),
                 endpoint="deadcourses"),

            # course-specific pages
            rule("/docs/<identifier:academy>/<identifier:course>/",
                 methods=("GET", "HEAD"), endpoint="course"),
            rule("/docs/<identifier:academy>/<identifier:course>/!delete",
                 methods=("POST",), endpoint="deletecourse"),
            rule("/docs/<identifier:academy>/<identifier:course>/!undelete",
                 methods=("POST",), endpoint="undeletecourse"),
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

    def connectdb(self):
        """Connect to the session database and create missing tables."""
        sessiondb = sqlite3.connect(self.sessiondbpath)
        cur = sessiondb.cursor()
        # Disable safety -- this increases performance (in a relevant way);
        # if the sessiondb should be lost at some point it's not uber-tragic
        cur.execute("PRAGMA synchronous = OFF;")
        cur.execute(SessionHandler.create_table)
        sessiondb.commit()
        return sessiondb

    def buildurl(self, rs: RequestState, endpoint: str,
                 args: typing.Dict[str, typing.Any]) -> str:
        """Looks up up the given endpoint in the routingmap and builds the
        corresponding url with the passed args. Missing args are added if the
        given endpoint requests them and they are present in the request uri as
        parsed by werkzeug's routing and stored in rs.endpoint_args.

        @param endpoint: an endpoint from self.routingmap
        @param args: a mapping from rule parameters to their values
        """
        assert isinstance(endpoint, str)
        buildargs = dict()
        for key, value in rs.endpoint_args.items():
            if self.routingmap.is_endpoint_expecting(endpoint, key):
                buildargs[key] = value
        buildargs.update(args)
        return rs.mapadapter.build(endpoint, buildargs)

    def staticjoin(self, name: str, rs: RequestState) -> str:
        """
        @param name: filename to serve statically
        @returns: url for the file
        """
        assert isinstance(name, str)
        ## If staticservepath is a full url, the join is the staticservepath.
        static = urlparse.urljoin(rs.request.url_root, self.staticservepath)
        return urlparse.urljoin(static, name)

    def mathjaxjoin(self, name: str, rs: RequestState) -> str:
        """
        @param name: filename to serve from mathjax
        @returns: url for the file
        """
        assert isinstance(name, str)
        ## If mathjaxuri is a full url, the join is the mathjaxuri.
        mathjax = urlparse.urljoin(rs.request.url_root, self.mathjaxuri)
        return urlparse.urljoin(mathjax, name)

    def getAcademy(self, name: str, user: typing.Optional[User] = None) -> \
            Academy:
        """
        look up an academy for a given name. If none is found raise a
        werkzeug.exceptions.NotFound.

        @raises werkzeug.exceptions.HTTPException:
        """
        assert isinstance(name, str)
        try:
            common.validateInternalName(name)
            nameb = name.encode("utf8")
            common.validateExistence(self.acapath, nameb)
        except CheckError:
            raise werkzeug.exceptions.NotFound()
        aca = Academy(os.path.join(self.acapath, nameb), self.listGroups)
        if user is not None and not user.allowedRead(aca):
            raise werkzeug.exceptions.Forbidden()
        return aca

    def getCourse(self, aca: Academy, coursename: str,
                  user: typing.Optional[User] = None) -> Course:
        """
        @raises werkzeug.exceptions.HTTPException:
        """
        assert isinstance(coursename, str)
        c = aca.getCourse(coursename) # checks name
        if c is None:
            raise werkzeug.exceptions.NotFound()
        if user is not None and not user.allowedRead(aca, c):
            raise werkzeug.exceptions.Forbidden()
        return c

    def createAcademy(self, name: str, title: str, groups) -> Academy:
        """
        create an academy. If the user data is malformed raise a CheckError.

        @raises CheckError:
        """
        assert isinstance(name, str)
        assert isinstance(title, str)
        assert all(isinstance(group, str) for group in groups)
        common.validateInternalName(name)
        nameb = name.encode("utf8")
        common.validateNonExistence(self.acapath, nameb)
        common.validateTitle(title)
        common.validateGroups(groups, self.listGroups())
        path = os.path.join(self.acapath, nameb)
        os.makedirs(path)
        aca = Academy(path, self.listGroups)
        aca.settitle(title)
        aca.setgroups(groups)
        return aca

    def listAcademies(self) -> typing.List[Academy]:
        ret = [self.getAcademy(p.decode("utf8"))
               for p in os.listdir(self.acapath)]
        ret.sort(key=operator.attrgetter('name'))
        return ret

    def listGroups(self) -> typing.Dict[str, str]:
        """
        @returns: a dict of all groups with their titles as values
        """
        try:
            config = configparser.ConfigParser()
            config.read_string(self.groupstore.content().decode("utf8"))
        except configparser.ParsingError as err:
            return {}
        ret = {}
        for group in config.sections():
            ret[group] = config.get(group, 'title')
        return ret

    @Request.application
    def __call__(self, request):
        mapadapter = self.routingmap.bind_to_environ(request.environ)
        self.userdb.load()
        rs = RequestState(request, self.sessionhandler, self.userdb, mapadapter)
        try:
            endpoint, args = mapadapter.match()
            ## grab a copy of the parameters for url building
            rs.endpoint_args = args
            return getattr(self, "do_%s" % endpoint)(rs, **args)
        except werkzeug.exceptions.HTTPException as e:
            return e

    def check_login(self, rs: RequestState) -> None:
        """
        @raises TemporaryRequestRedirect: unless the user is logged in
        """
        if rs.user is None:
            raise TemporaryRequestRedirect(rs.request.url_root)

    def do_file(self, rs: RequestState, filestore: Storage, template: str,
                extraparams: typing.Dict = dict()):
        """
        Function to generically handle editing a single file.

        @param filestore: the file which should be edited
        @param template: the template with which to render the edit mask
        @param extraparams: any further params the template needs
        """
        assert isinstance(template, str)
        version, content = filestore.startedit()
        return self.render_file(rs, template, version.decode("utf8"),
                                content.decode("utf8"), extraparams=extraparams)

    def do_filesave(self, rs: RequestState, filestore: Storage, template: str,
                    checkhook: typing.Optional[typing.Callable] = None,
                    savehook: typing.Optional[typing.Callable] = None,
                    extraparams: typing.Dict = dict()):
        """
        Function to generically handle saving a single file.

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
            error = CheckError("Es ist ein Konflikt mit einer anderen Änderung aufgetreten!",
                               "Bitte löse den Konflikt auf und speichere danach erneut.")
            return self.render_file(rs, template, version, content, ok=False,
                                    error = error, extraparams=extraparams)
        if not savehook is None:
            savehook()
        return self.render_file(rs, template, version, content, ok=True,
                                extraparams=extraparams)

    def do_property(self, rs: RequestState, getter, template: str,
                    extraparams: typing.Dict = dict()):
        """
        Function to generically handle editing a single property. The showy
        part.

        @type getter: callale
        @param getter: getter function for the property to edit
        @param template: the template with which to render the edit mask
        @param extraparams: any further params the template needs
        """
        assert isinstance(template, str)
        content = getter()
        assert isinstance(content, str)
        return self.render_property(rs, template, content,
                                    extraparams=extraparams)

    def do_propertysave(self, rs: RequestState, setter, template: str,
                        extraparams: typing.Dict = dict()):
        """
        Function to generically handle editing a single property. The worker
        part.

        @type setter: callable
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

    def do_start(self, rs: RequestState):
        if rs.user is None:
            return self.render_start(rs)
        return self.render_index(rs)

    def do_login(self, rs: RequestState):
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

    def do_logout(self, rs: RequestState):
        rs.logout()
        return self.render_start(rs)

    def do_index(self, rs: RequestState):
        self.check_login(rs)
        return self.render_index(rs, None)

    def do_groupindex(self, rs: RequestState, *,
                      group: typing.Optional[str] = None):
        self.check_login(rs)
        return self.render_index(rs, group)

    def do_academy(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        return self.render_academy(rs, aca)

    def do_course(self, rs: RequestState, *, academy: str, course: str):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        return self.render_course(rs, aca, c)

    def do_showdeadpages(self, rs: RequestState, *, academy: str, course: str):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_deadpages(rs, aca, c)

    def do_showdeadblobs(self, rs: RequestState, *, academy: str, course: str,
                         page: int):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_deadblobs(rs, aca, c, page)

    def do_createcoursequiz(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        return self.render_createcoursequiz(rs, aca)

    def do_createcourse(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        name = rs.request.form["name"] # FIXME: raises KeyError
        title = rs.request.form["title"] # FIXME: raises KeyError
        try:
            aca.createCourse(name, title)
        except CheckError as error:
            return self.render_createcoursequiz(rs, aca, ok=False,
                                                error = error)
        return self.render_academy(rs, aca)

    def do_createacademyquiz(self, rs: RequestState):
        self.check_login(rs)
        if not rs.user.mayCreate():
            return werkzeug.exceptions.Forbidden()
        return self.render_createacademyquiz(rs)

    def do_createacademy(self, rs: RequestState):
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

    def do_styleguide(self, rs: RequestState):
        return self.do_styleguidetopic(rs, topic="index")

    def do_styleguidetopic(self, rs: RequestState, *, topic: str):
        assert isinstance(topic, str)
        if topic not in os.listdir(os.path.join(self.templatepath,
                                                "style")):
            raise werkzeug.exceptions.NotFound()
        return self.render_styleguide(rs, topic)

    def do_deletecourse(self, rs: RequestState, *, academy: str, course: str):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        c.delete()
        return self.render_academy(rs, aca)

    def do_undeletecourse(self, rs: RequestState, *, academy: str,
                          course: str):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        c.undelete()
        return self.render_academy(rs, aca)

    def do_createpage(self, rs: RequestState, *, academy: str, course: str):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.newpage(user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_delete(self, rs: RequestState, *, academy: str, course: str,
                  page: int):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.delpage(page, user=rs.user.name)
        return self.render_course(rs, aca, c)

    def do_blobdelete(self, rs: RequestState, *, academy: str, course: str,
                      page: int, blob: int):
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        c.delblob(blob, user=rs.user.name)
        return self.render_show(rs, aca, c, page)

    def do_relink(self, rs: RequestState, *, academy: str, course: str):
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

    def do_relinkblob(self, rs: RequestState, *, academy: str, course: str,
                      page: int):
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

    def do_showblob(self, rs: RequestState, *, academy: str, course: str,
                    page: int, blob: int):
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_showblob(rs, aca, c, page, blob)

    def do_editblob(self, rs: RequestState, *, academy: str, course: str,
                    page: int, blob: int):
        assert academy is not None and course is not None and \
               page is not None and blob is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c) or not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_editblob(rs, aca, c, page, blob)

    def do_saveblob(self, rs: RequestState, *, academy: str, course: str,
                    page: int, blob: int):
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

    def do_md5blob(self, rs: RequestState, *, academy: str, course: str,
                   page: int, blob: int):
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

    def do_downloadblob(self, rs: RequestState, *, academy: str, course: str,
                        page: int, blob: int):
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

    def do_rcs(self, rs: RequestState, *, academy: str, course: str,
               page: int):
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

    def do_raw(self, rs: RequestState, *, academy: str, course: str):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedRead(aca, c):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/octet-stream"
        def export_iterator(course):
            tarwriter = common.TarWriter(gzip=True)
            for chunk in course.rawExportIterator(tarwriter):
                yield chunk
            yield tarwriter.close()
        rs.response.response = export_iterator(c)
        filename = (b"%s_%s.tar.gz" % (aca.name, c.name)).decode("ascii")
        rs.response.headers['Content-Disposition'] = \
                "attachment; filename=" + filename
        return rs.response

    def do_rawacademy(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedRead(aca):
            return werkzeug.exceptions.Forbidden()
        if not rs.user.mayExport(aca):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/octet-stream"
        def export_iterator(academy):
            tarwriter = common.TarWriter(gzip=True)
            for chunk in academy.rawExportIterator(tarwriter):
                yield chunk
            yield tarwriter.close()
        rs.response.response = export_iterator(aca)
        filename = "%s.tar.gz" % aca.name.decode("ascii")
        rs.response.headers['Content-Disposition'] = \
                "attachment; filename=" + filename
        return rs.response

    def do_export(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.mayExport(aca):
            return werkzeug.exceptions.Forbidden()
        rs.response.content_type = "application/octet-stream"
        prefix = b"texexport_" + aca.name
        def export_iterator(aca, static, prefix):
            tarwriter = common.TarWriter(gzip=True)
            tarwriter.pushd(prefix)
            for chunk in aca.texExportIterator(tarwriter,
                                               static=static):
                yield chunk
            tarwriter.popd()
            yield tarwriter.close()
        rs.response.response = export_iterator(aca, self.staticexportdir,
                                               prefix)
        rs.response.headers['Content-Disposition'] = \
                "attachment; filename=%s.tar.gz" % prefix
        return rs.response

    def do_moveup(self, rs: RequestState, *, academy: str, course: str):
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

    def do_page(self, rs: RequestState, *, academy: str, course: str,
                page: int):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        return self.render_show(rs, aca, c, page)

    def do_edit(self, rs: RequestState, *, academy: str, course: str,
                page: int):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        version, content = c.editpage(page)
        return self.render_edit(rs, aca, c, page, version, content)

    def do_addblob(self, rs: RequestState, *, academy: str, course: str,
                   page: int):
        assert academy is not None and course is not None and page is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedWrite(aca, c):
            return werkzeug.exceptions.Forbidden()
        return self.render_addblob(rs, aca, c, page)

    def do_uploadblob(self, rs: RequestState, *, academy: str, course: str,
                      page: int):
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

    def do_attachblob(self, rs: RequestState, *, academy: str, course: str,
                      page: int):
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

    def do_save(self, rs: RequestState, *, academy: str, course: str,
                page: int):
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

    def do_academygroups(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        return self.render_academygroups(rs, aca)

    def do_academygroupssave(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        groups = rs.request.form.getlist("groups") # FIXME: raises KeyError
        try:
            aca.setgroups(groups)
        except CheckError as error:
            return self.render_academygroups(rs, aca,  ok = False,
                                             error = error)
        return self.render_academygroups(rs, aca, ok = True)

    def do_deadcourses(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        return self.render_deadcourses(rs, aca)

    def do_academytitle(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_property(rs, aca.gettitle,
                                "academytitle.html",
                                extraparams={'academy': aca.view()})

    def do_academytitlesave(self, rs: RequestState, *, academy: str):
        assert academy is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_propertysave(rs, aca.settitle,
                                    "academytitle.html",
                                    extraparams = {'academy': aca.view()})

    def do_coursetitle(self, rs: RequestState, *, academy: str, course: str):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_property(rs, c.gettitle,
                                "coursetitle.html",
                                extraparams={'academy': aca.view(),
                                             'course': c.view()})

    def do_coursetitlesave(self, rs: RequestState, *, academy: str,
                           course: str):
        assert academy is not None and course is not None
        self.check_login(rs)
        aca = self.getAcademy(academy, rs.user)
        c = self.getCourse(aca, course, rs.user)
        if not rs.user.allowedMeta(aca):
            return werkzeug.exceptions.Forbidden()
        return self.do_propertysave(rs, c.settitle,
                                    "coursetitle.html",
                                    extraparams={'academy': aca.view(),
                                                 'course': c.view()})

    def do_admin(self, rs: RequestState):
        self.check_login(rs)
        if not rs.user.isAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, self.userdb.storage, "admin.html")

    def do_adminsave(self, rs: RequestState):
        self.check_login(rs)
        if not rs.user.isAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, self.userdb.storage, "admin.html",
                                checkhook = common.validateUserConfig,
                                savehook = self.userdb.load)

    def do_groups(self, rs: RequestState):
        self.check_login(rs)
        if not rs.user.isSuperAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_file(rs, self.groupstore, "groups.html")

    def do_groupssave(self, rs: RequestState):
        self.check_login(rs)
        if not rs.user.isSuperAdmin():
            return werkzeug.exceptions.Forbidden()
        return self.do_filesave(rs, self.groupstore, "groups.html",
                                checkhook = common.validateGroupConfig)

    ### here come the renderer

    def render_start(self, rs: RequestState):
        return self.render("start.html", rs)

    def render_styleguide(self, rs: RequestState, topic: str):
        assert isinstance(topic, str)
        params = dict(
            topic = topic,
            includepath=os.path.join("style", topic)
            )
        return self.render("style.html", rs, params)

    def render_edit(self, rs: RequestState, theacademy: Academy,
                    thecourse: Course, thepage: int, theversion: str,
                    thecontent: str, ok: typing.Optional[bool] = None):
        assert isinstance(theversion, str)
        assert isinstance(thecontent, str)
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

    def render_index(self, rs: RequestState,
                     group: typing.Optional[str] = None):
        if group is None:
            group = rs.user.defaultGroup()
        params = dict(
            academies=[academy.view() for academy in self.listAcademies()],
            allgroups=self.listGroups(),
            group=group)
        return self.render("index.html", rs, params)

    def render_academy(self, rs: RequestState, theacademy: Academy):
        return self.render("academy.html", rs,
                           dict(academy=theacademy.view()))

    def render_deadcourses(self, rs: RequestState, theacademy: Academy):
        return self.render("deadcourses.html", rs,
                           dict(academy=theacademy.view()))

    def render_deadblobs(self, rs: RequestState, theacademy: Academy,
                         thecourse: Course, thepage: int):
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            blobs=[thecourse.viewblob(i) for i in thecourse.listdeadblobs()])
        return self.render("deadblobs.html", rs, params)

    def render_deadpages(self, rs: RequestState, theacademy: Academy,
                         thecourse: Course):
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view())
        return self.render("dead.html", rs, params)

    def render_course(self, rs: RequestState, theacademy: Academy,
                      thecourse: Course):
        courseview = thecourse.view()
        theestimate = Estimate.fromNothing()
        for x in courseview['outlines']:
            theestimate += x.estimate
        params = dict(
            academy=theacademy.view(),
            course=courseview,
            estimate=theestimate)
        return self.render("course.html", rs, params)

    def render_addblob(self, rs: RequestState, theacademy: Academy,
                       thecourse: Course, thepage: int, ok=None, error=None):
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            ok=ok,
            error=error,
            allowMathChange = False)
        return self.render("addblob.html", rs, params)

    def render_uploadblob(self, rs: RequestState, theacademy: Academy,
                          thecourse: Course, thepage: int):
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            allowMathChange = False)
        return self.render("uploadblob.html", rs, params)

    def render_showblob(self, rs: RequestState, theacademy: Academy,
                        thecourse: Course, thepage: int, blob: int,
                        blobhash: typing.Optional[str] = None):
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            blob=thecourse.viewblob(blob),
            blobhash=blobhash)
        return self.render("showblob.html", rs, params)

    def render_editblob(self, rs: RequestState, theacademy: Academy,
                        thecourse: Course, thepage: int, blob: int,
                        ok: typing.Optional[bool] = None,
                        error: typing.Optional[CheckError] = None):
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            blob=thecourse.viewblob(blob),
            ok=ok,
            error=error,
            allowMathChange = False)
        return self.render("editblob.html", rs, params)

    def render_createcoursequiz(self, rs: RequestState, theacademy: Academy,
                                ok: typing.Optional[bool] = None,
                                error: typing.Optional[CheckError] = None):
        params = dict(academy=theacademy.view(),
                      ok=ok,
                      error=error,
                      allowMathChange = False)
        return self.render("createcoursequiz.html", rs, params)

    def render_createacademyquiz(self, rs: RequestState,
                                 ok: typing.Optional[bool] = None,
                                 error: typing.Optional[CheckError] = None):
        params = dict(ok=ok,
                      error=error,
                      allgroups=self.listGroups(),
                      allowMathChange = False)
        return self.render("createacademyquiz.html", rs, params)

    def render_academygroups(self, rs: RequestState, theacademy: Academy,
                             ok=None, error=None):
        params = dict(academy = theacademy.view(),
                      allgroups = self.listGroups(),
                      allowMathChange = False,
                      ok = ok,
                      error = error)
        return self.render("academygroups.html", rs, params)

    def render_show(self, rs: RequestState, theacademy: Academy,
                    thecourse: Course, thepage: int, saved: bool = False):
        parsed = dfLineGroupParser(thecourse.showpage(thepage))
        theblobs = [thecourse.viewblob(i) for i in thecourse.listblobs(thepage)]
        theestimate = parsed.toEstimate() + Estimate.fromBlobs(theblobs)
        params = dict(
            academy=theacademy.view(),
            course=thecourse.view(),
            page=thepage,
            commit = thecourse.getcommit(thepage),
            content=parsed.toHtml(),
            estimate=theestimate,
            saved=saved,
            blobs=theblobs)
        return self.render("show.html", rs, params)

    def render_file(self, rs: RequestState, templatename: str, theversion: str,
                    thecontent: str, ok: typing.Optional[bool] = None,
                    error: typing.Optional[CheckError] = None,
                    extraparams: typing.Dict = dict()):
        assert isinstance(templatename, str)
        assert isinstance(theversion, str)
        assert isinstance(thecontent, str)
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

    def render_property(self, rs: RequestState, templatename: str,
                        thecontent: str, ok: typing.Optional[bool] = None,
                        error: typing.Optional[CheckError] = None,
                        extraparams: typing.Dict = dict()):
        assert isinstance(templatename, str)
        assert isinstance(thecontent, str)
        params = dict(
            content=thecontent,
            ok=ok,
            error=error,
            allowMathChange = False)
        params.update(extraparams)
        return self.render(templatename, rs, params)

    def render(self, templatename: str, rs: RequestState,
               extraparams: typing.Dict = dict()):
        assert isinstance(templatename, str)
        rs.response.content_type = "text/html; charset=utf8"
        allowMathChange = True
        if rs.request.method == "POST":
            allowMathChange = False
        params = dict(
            user = rs.user,
            commitid=commitid,
            form=rs.request.form,
            buildurl=lambda name, kwargs=dict(): self.buildurl(rs, name, kwargs),
            staticjoin = lambda name: self.staticjoin(name, rs),
            mathjaxjoin = lambda name: self.mathjaxjoin(name, rs),
            allowMathChange = allowMathChange)
        params.update(extraparams)
        template = self.jinjaenv.get_template(templatename)
        rs.response.data = template.render(params).encode("utf8")
        return rs.response
