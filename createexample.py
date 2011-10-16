#!/usr/bin/python

import os
from main import Application
import storage
import user


if __name__ == "__main__":
    try:
        os.mkdir("work")
    except OSError:
        pass
    mystore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(mystore)
    userdb.addUser("arthur", "dokubeauftragter", "mypass", dict([("akademie_read_pa2010", True), ("akademie_read_za2011", True), ("akademie_read_za2011_course01", True)]))
    userdb.addUser("bob", "dokuteam", "secret", dict([("akademie_read_pa2010", True), ("akademie_write_pa2010", True), ("df_useradmin", True), ("akademie_read_za2011", True), ("akademie_read_za2011_course01", True),  ("akademie_write_za2011_course01", True),  ("akademie_read_za2011_course02", True)]))
    userdb.store()
    try:
        os.mkdir("df")
    except OSError:
        pass
    userdbstore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(userdbstore)
    userdb.load()
    app = Application(userdb, './df/')
    aca = app.createAcademy('za2011-1', 'Beste Akademie ever', ["cde"])
    aca.createCourse('course01', "Internethumor und seine Schuld am Weltuntergang")
    aca.createCourse('course02', "Helenistische Heldenideale")
    aca.getCourse('course01').newpage()
    aca.getCourse('course01').newpage()
    aca.getCourse('course02').newpage()
    aca.getCourse('course02').newpage()
    aca.getCourse('course02').newpage()
    (version, cont) = aca.getCourse('course01').editpage(0)
    aca.getCourse('course01').savepage(0, version, """[Example Section]
This is an example with some nice math: $e^{i\pi}+1=0$.
""", "init")
