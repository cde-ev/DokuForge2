#!/usr/bin/env python

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
    with open(os.path.join(workdir, "dokuforge", "versioninfo.py"),
              "w") as verfile:
        verfile.write('commitid = u"%s"\n' % commitid)

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
