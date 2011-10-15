#!/usr/bin/python

import os
import storage
import user

if __name__ == "__main__":
    os.mkdir("work")
    mystore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(mystore)
    userdb.addUser("arthur", "dokubeauftragter", "mypass", dict([("akademie_read_pa2010", True)]))
    userdb.addUser("bob", "dokuteam", "secret", dict([("akademie_read_pa2010", True), ("akademie_write_pa2010", True)]))
    userdb.store()
