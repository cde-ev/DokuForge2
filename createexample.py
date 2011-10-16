#!/usr/bin/python

import os
from main import Application
import storage
import user

def createaca(name, title, groups, courses):
    aca = app.createAcademy(name, title, groups)
    for c in courses:
        aca.createCourse(c[0], c[1])
        for i in range(c[2]):
            aca.getCourse(c[0]).newpage()
    return aca

if __name__ == "__main__":
    try:
        os.mkdir("work")
    except OSError:
        pass
    mystore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(mystore)n
    userdb.addUser("arthur", "dokubeauftragter", "mypass",
                   dict([("akademie_read_pa2010", True),
                         ("akademie_read_za2011", True),
                         ("akademie_read_za2011_course01", True)]))
    userdb.addUser("bob", "dokuteam", "secret",
                   dict([("akademie_read_pa2010", True),
                         ("akademie_write_pa2010", True),
                         ("df_useradmin", True),
                         ("akademie_read_za2011-1", True),
                         ("akademie_read_za2011-1_course01", True),
                         ("akademie_write_za2011-1_course01", True),
                         ("akademie_read_za2011-1_course02", True),
                         ("akademie_read_ya2011-1", True),
                         ("akademie_write_ya2011-1", True),
                         ("akademie_read_ya2011-1_course01", True),
                         ("akademie_write_ya2011-1_course01", True),
                         ("akademie_read_ya2011-1_course02", True),
                         ("akademie_read_xa2011-1", True),
                         ("akademie_read_xa2011-1_course01", True)]))
    userdb.store()
    try:
        os.mkdir("df")
    except OSError:
        pass
    userdbstore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(userdbstore)
    userdb.load()
    app = Application(userdb, './df/')
    aca = createaca("za2011-1", "Beste Akademie ever", ["cde"],
                    [('course01',"Internethumor und seine Schuld am Weltuntergang", 3),
                     ('course02', "Helenistische Heldenideale", 2)]
    (version, cont) = aca.getCourse('course01').editpage(0)
    aca.getCourse('course01').savepage(0, version, """[Example Section]
This is an example with some nice math: $e^{i\pi}+1=0$.
""", "init")
    aca = createaca("ya2011-1", "Why? Akademie", ["qed", "cde"],
                    [('course01',"Kursqualitaet und ihre Kontrolle", 2),
                     ('course02',"Die Hedonistische Internationale", 3),
                     ('course03', "Orgateams und ihre Geschichte", 4)]

    aca = createaca("xa2011-1", "X-Akademie", ["qed"],
                    [('course01',"Area51", 2),
                     ('course02',"Fox Mulders Biographie", 3),
                     ('course03', "Selbstverteidigung gegen Poltergeister", 4)]
