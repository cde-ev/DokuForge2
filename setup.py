#!/usr/bin/env python

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

from distutils.core import setup
import os
import subprocess

workdir = os.path.dirname(os.path.realpath(__file__))

def add_versioninfo():
    try:
        p = subprocess.Popen(["git", "show", "-s", "--format=%H"],
                             stdout=subprocess.PIPE,
                             cwd=workdir)
    except OSError:
        return
    commitid, _ = p.communicate()
    if p.returncode != 0:
        return
    commitid = commitid.strip()
    with file(os.path.join(workdir, "dokuforge", "versioninfo.py"),
              "w") as verfile:
        verfile.write('commitid = "%s"\n' % commitid)

def clean_versioninfo():
    try:
        os.unlink(os.path.join(workdir, "dokuforge", "versioninfo.py"))
    except OSError:
        pass

add_versioninfo()
setup(name="dokuforge",
      packages=["dokuforge"],
      package_data=dict(dokuforge=["templates/*.html",
                                   "templates/style/*",
                                   "static/*.css"]))
clean_versioninfo()
