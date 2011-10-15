#!/usr/bin/python

import os
from main import Application
import storage
import user


if __name__ == "__main__":
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
