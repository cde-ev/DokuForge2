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
Moderate server listening on scgi://localhost:4000/ with an asynchronous worker.
"""

from wsgitools.scgi.asynchronous import SCGIServer

from dokuforge import buildapp

def main():
    app = buildapp()
    SCGIServer(app, 4000).run()

if __name__ == '__main__':
    main()
