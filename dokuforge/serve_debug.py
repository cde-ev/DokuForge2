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
#!/usr/bin/env python
"""
Simple server listening on http://localhost:8800/ with a traceback middleware
and logging requests to stdout.

WARNING: anyone producing an exception can execute any python code via http
"""

import logging
from wsgiref.simple_server import make_server

from werkzeug.debug import DebuggedApplication

from dokuforge import buildapp

def main():
    logging.basicConfig(level=logging.DEBUG)
    app = buildapp()
    app = DebuggedApplication(app, evalex=True)
    make_server("localhost", 8800, app).serve_forever()

if __name__ == '__main__':
    main()
