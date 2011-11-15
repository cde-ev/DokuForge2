#!/usr/bin/env python

from distutils.core import setup
import os
import subprocess

def add_versioninfo():
    try:
        p = subprocess.Popen(["git", "show", "-s", "--format=%H"],
                             stdout=subprocess.PIPE)
    except OSError:
        return
    commitid, _ = p.communicate()
    if p.returncode != 0:
        return
    commitid = commitid.strip()
    with file(os.path.join(os.path.dirname(__file__), "dokuforge",
                           "versioninfo.py"), "w") as verfile:
        verfile.write('commitid = "%s"\n' % commitid)

def clean_versioninfo():
    try:
        os.unlink(os.path.join(os.path.dirname(__file__), "dokuforge",
                               "versioninfo.py"))
    except OSError:
        pass

add_versioninfo()
setup(name="dokuforge",
      packages=["dokuforge"],
      package_data=dict(dokuforge=["templates/*.html",
                                   "templates/style/*",
                                   "static/*.css"]))
clean_versioninfo()
