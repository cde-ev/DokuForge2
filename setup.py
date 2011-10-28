#!/usr/bin/env python

from distutils.core import setup

setup(name="dokuforge",
      packages=["dokuforge"],
      package_data=dict(dokuforge=["templates/*.html",
                                   "templates/sytle/*",
                                   "static/*.css"]))
