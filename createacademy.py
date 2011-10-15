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
    acadbstore = storage.Storage('work', 'acadb')
    app = Application(userdb, acadbstore)
    app.createAcademy('za2011-1', 'Beste Akademie ever', ["cde"])
