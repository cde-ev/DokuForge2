# Copyright (c) 2012, Klaus Aehlig, Helmut Grohne, Markus Oehme
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the three-clause BSD license.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# You should have received a copy of the Three-Clause BSD License
# along with this program in the file COPYING.
# If not, see <http://opensource.org/licenses/bsd-3-clause>
import os.path

from werkzeug.wsgi import SharedDataMiddleware

from dokuforge.application import Application
from dokuforge.paths import PathConfig

def buildapp(pathconfig=PathConfig()):
    """
    @type pathconfig: PathConfig
    """
    app = Application(pathconfig)
    app = SharedDataMiddleware(
        app, {"/%s" % pathconfig.staticservepath:
              os.path.join(os.path.dirname(__file__), "static")})
    return app
