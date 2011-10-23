#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from main import Application
import storage
import user
from werkzeug.datastructures import FileStorage

def createaca(app, name, title, groups, courses):
    assert isinstance(title, unicode)
    aca = app.createAcademy(name, title, groups)
    for c in courses:
        aca.createCourse(c[0], c[1])
        for i in range(c[2]):
            aca.getCourse(c[0]).newpage()
    return aca

def main(size=100):
    """
    @param size: regulate size of example from 0 for empty to 100 for complete
    """
    try:
        os.mkdir("work")
    except OSError:
        pass
    mystore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(mystore)
    if size > 10:
        userdb.addUser(u"arthur", u"dokubeauftragter", u"mypass",
                       dict([(u"akademie_read_pa2010", True),
                             (u"akademie_read_za2011", True),
                             (u"akademie_read_za2011_course01", True)]))
    userdb.addUser(u"bob", u"dokuteam", u"secret",
                   dict([(u"akademie_read_pa2010", True),
                         (u"akademie_write_pa2010", True),
                         (u"df_admin", True),
                         (u"df_superadmin", True),
                         (u"akademie_read_za2011-1", True),
                         (u"akademie_read_za2011-1_course01", True),
                         (u"akademie_write_za2011-1_course01", True),
                         (u"akademie_read_za2011-1_course02", True),
                         (u"akademie_read_ya2011-1", True),
                         (u"akademie_write_ya2011-1", True),
                         (u"akademie_read_ya2011-1_course01", True),
                         (u"akademie_write_ya2011-1_course01", True),
                         (u"akademie_read_ya2011-1_course02", True),
                         (u"df_export", True),
                         (u"df_show", True)]))
    userdb.store()
    mygroupstore = storage.Storage('work', 'groupdb')
    mygroupstore.store("""[cde]
title = CdE-Akademien

[qed]
title = QED-Akademien

[old-cde]
title = Archiv aelterer CdE-Akademien
""")
    try:
        os.mkdir("df")
    except OSError:
        pass
    userdbstore = storage.Storage('work', 'userdb')
    userdb = user.UserDB(userdbstore)
    userdb.load()
    app = Application(userdb, mygroupstore, './df/', "./templates/", "./style/")
    if size > 50:
        aca = createaca(app, u"za2011-1", u"Beste Akademie ever", [u"cde"],
                        [(u'course01',u"Internethumor und seine Schuld am Weltuntergang", 3),
                         (u'course02', u"Helenistische Heldenideale", 2)])
        (version, cont) = aca.getCourse(u'course01').editpage(0)
        aca.getCourse(u'course01').savepage(0, version, u"""[Example Section]
        This is an example with some nice math: $e^{i\pi}+1=0$.
        """, u"init")
        aca.getCourse(u'course01').attachblob(0, FileStorage(filename = "academy.py", stream=file("./academy.py",mode="r")), u"Ein lustiges Bild", u"myx", user=u"init")
        aca.getCourse(u'course01').attachblob(1, FileStorage(filename = "storage.py", stream=file("./storage.py", mode="r")), u"Ein anderes lustiges Bild", u"somey", user=u"init")
        aca.getCourse(u'course01').attachblob(0, FileStorage(filename = "course.py", stream=file("./course.py", mode="r")), u"Noch ein lustiges Bild", u"ultimatez", user=u"init")
    if size > 25:
        aca = createaca(app, u"ya2011-1", u"Why? Akademie", [u"qed", u"cde"],
                        [(u'course01',u"Kursqualitaet und ihre Kontrolle", 2),
                         (u'course02',u"Die Hedonistische Internationale", 3),
                         (u'course03', u"Orgateams und ihre Geschichte", 4)])

    aca = createaca(app, u"xa2011-1", u"X-Akademie", [u"cde"],
                    [(u'course01',u"Area51", 2),
                     (u'course02',u"Fox Mulders Biographie", 3),
                     (u'course03', u"Selbstverteidigung gegen Poltergeister", 4)])

if __name__ == '__main__':
    main()
