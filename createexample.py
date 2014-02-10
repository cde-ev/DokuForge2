#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

try:
    unicode
except NameError:
    unicode = str

from werkzeug.datastructures import FileStorage

from dokuforge.application import Application
from dokuforge.paths import PathConfig

def createaca(app, name, title, groups, courses):
    assert isinstance(title, unicode)
    aca = app.createAcademy(name, title, groups)
    for c in courses:
        aca.createCourse(c[0], c[1])
        for i in range(c[2]):
            aca.getCourse(c[0]).newpage()
    return aca

def main(size=100, pc=PathConfig()):
    """
    @param size: regulate size of example from 0 for empty to 100 for complete
    @type pc: PathConfig
    """
    try:
        os.makedirs(pc.admindir)
    except OSError:
        pass
    try:
        os.makedirs(pc.staticexportdir)
    except OSError:
        pass
    userdbstore = pc.userdbstore
    if size > 10:
        userdbstore.store("""
[arthur]
status = cde_dokubeauftragter
password = mypass
permissions = akademie_read_pa2010 True,akademie_read_za2011-1 True,kurs_read_za2011-1_course01 True

[bob]
name = bob
status = cde_dokuteam
password = secret
permissions = df_show True,akademie_read_za2011-1 True,kurs_write_ya2011-1_course01 True,kurs_write_za2011-1_course01 True,df_export True,df_superadmin True,akademie_write_pa2010 True,kurs_read_ya2011-1_course02 True,akademie_read_ya2011-1 True,kurs_read_za2011-1_course01 True,akademie_write_ya2011-1 True,kurs_read_za2011-1_course02 True,akademie_read_pa2010 True,df_admin True,kurs_read_ya2011-1_course01 True
""")
    else:
        userdbstore.store("""
[bob]
name = bob
status = cde_dokuteam
password = secret
permissions = df_show True,akademie_read_za2011-1 True,kurs_write_ya2011-1_course01 True,kurs_write_za2011-1_course01 True,df_export True,df_superadmin True,akademie_write_pa2010 True,kurs_read_ya2011-1_course02 True,akademie_read_ya2011-1 True,kurs_read_za2011-1_course01 True,akademie_write_ya2011-1 True,kurs_read_za2011-1_course02 True,akademie_read_pa2010 True,df_admin True,kurs_read_ya2011-1_course01 True
""")
    mygroupstore = pc.groupstore
    mygroupstore.store("""[cde]
title = CdE-Akademien

[qed]
title = QED-Akademien

[old-cde]
title = Archiv aelterer CdE-Akademien
""")
    try:
        os.mkdir(pc.dfdir)
    except OSError:
        pass
    userdb = pc.loaduserdb()
    app = Application(pc)
    if size > 50:
        aca = createaca(app, u"za2011-1", u"Beste Akademie ever", [u"cde"],
                        [(u'course01',u"Internethumor und seine Schuld am Weltuntergang", 3),
                         (u'course02', u"Helenistische Heldenideale", 2)])
        (version, cont) = aca.getCourse(u'course01').editpage(0)
        aca.getCourse(u'course01').savepage(0, version, 
u"""[Example Section]
This is an example with some nice math: $e^{i\pi}+1=0$.

And even a mathematical limmerick!

$$\int_1^{\sqrt[3]{3}} z^2 dz \cdot \cos(\\frac{3\pi}{9}) = \ln(\sqrt[3]{e})$$
""", 
        u"init")
        aca.getCourse(u'course01').attachblob(0, FileStorage(filename = "academy.py", stream=file("./dokuforge/academy.py",mode="r")), u"Ein lustiges Bild", u"myx", user=u"init")
        aca.getCourse(u'course01').attachblob(1, FileStorage(filename = "storage.py", stream=file("./dokuforge/storage.py", mode="r")), u"Ein anderes lustiges Bild", u"somey", user=u"init")
        aca.getCourse(u'course01').attachblob(0, FileStorage(filename = "course.py", stream=file("./dokuforge/course.py", mode="r")), u"Noch ein lustiges Bild", u"ultimatez", user=u"init")
    if size > 25:
        aca = createaca(app, u"ya2011-1", u"Why? Akademie", [u"qed", u"cde"],
                        [(u'course01',u"Kursqualitaet und ihre Kontrolle", 2),
                         (u'course02',u"Die Hedonistische Internationale", 3),
                         (u'course03', u"Orgateams und ihre Geschichte", 4)])

    if size > 0:
        aca = createaca(app, u"xa2011-1", u"X-Akademie", [u"cde"],
                        [(u'course01', u"Area51", 2), (u"course02", u"Markup test", 3)])
        (version, cont) = aca.getCourse(u'course02').editpage(1)
        aca.getCourse(u'course02').savepage(1, version, u"""
[Ueberschrift]
(Autor)

Hier ist ein
Paragrpah ueber 3
Zeilen.

[[Unterueberschrift]]
(Autor)

Und ein weiterer
Absatz.
(Man beachte, dass diese Klammer
keine Autorenangabe beinhaltet)

{ Das ist eine ednote

[und keine Ueberschrift]
}


{ Ednote: short }

Und es gibt auch sehr kurze eingebundene Ednotes
{(so wie diese hier, die eine } beinhaltet)}
Bla bla bla ...
{(dies ist auch ueber
zwei Zeilen -- ebenfalls mit } -- moeglich)}
Bla bla bla ...


{ Ednote:

  Mit Leerzeile! }

{((

Fancy Ednote, containing Code

for(i=0, i< 10; i++) {
  printf("%d\\n", i);
}

))}
  
{ Ednote }
Hier beginnt ein neuer Absatz.

Und nun noch eine Aufzaehlung.
- erstens
- zweitens
- drittens

Und eine numerierte Aufzaehlung.
1. erstens
2. zweitens
3. drittens

[Hier eine Ueberschrift, ohne
 Autorenangabe, ueber mehrere Zeilen
 hinweg]
Man beachte, dass die Ueberschrift unmittelbar
von einem Absatz gefolgt ist -- ohne Leerzeile
dazwischen.

[Ueberschrift]
(Autor Alpha,
 Autor Bravo)

Und ein weiterer Absatz.
Dieser enthaelt _betonten_ Text.
Und auch Mathematik, z.B. $x^2 + y^2$
oder auch $x_1 + x_2$.

Und dieser Absatz enthaelt boese
Mathematik wie $ \$ $ oder
$ \\\\$.

*Modularitaet* ist die Wesentliche Idee hinter
diesem Ansatz der Groupierung von Zeilen.

*Flexibilitaet fuer Erweiterungen* ist etwas,
worauf wir wohl nicht verzichten koennen.

*Description
Key
Words*
koennen ebenfalls ueber mehre Zeilenen
gehen.

Text text ...
{ sehr kurze, eingebunde ednote }
Noch ein neuer Absatz.

{ Ednote:
  hiervor tauchen keine zwei Zeilenumbrueche auf }

Und ein weiterer Absatz.
Danach kommen 2 getrennte Aufzaehungen.

- a
- b
- c

- x
- y
- z

ACRONYME sind z.B. microtypogrpahie-technisch interessant.
Zahlen wie 1000, 9999, 10000, 10001 und 1000000000 ebenfalls.

[Auch HIER in Ueberschriften und an 100000 anderen Orten!]
Beispielsweise am Satzende, wie HIER. Oder in Anfuehrungszeichen.
Er sagte: "10000 mal ist das schon gutgegangen. Warum diesmal
nicht?"

Und hier kommen noch Beispiele wie man's falsch machen kann.

[Ueberschrit ueber mehrere Zeilen,
 die aber keine Schliessende Klammern enthaelt

Und weiterer neuer Text. Bla Bla bla ...

[Und auch Autorenangaben kann man falsch machen]
(Autor Alpha,
 Autor Bravo

Normaler Text. Bla Bla bla ...

*Description ohne schliessenden Stern fuer das Keyword.

*Keyword ist dann einfach das erste Wort.

""",
        u"init")

if __name__ == '__main__':
    main()
