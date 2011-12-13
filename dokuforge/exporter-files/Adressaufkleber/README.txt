Beispiel-Adressendatei, so wie sie aus dem Datenbank-Export kommt, am
Ende von Hand erweitert um Externe und sonstige Empfänger.

python-Skript, das die Adressen nach Ausland (Land) und Inland
(Postleitzahl) sortiert und in eine .tex-Datei schreibt, die dann mit
pdflatex übersetzt werden kann.

Ole 20091014

Zum Vergleich der Kursfoto-Beschriftungen können folgende Kommandos hilfreich sein
./parser.py | sort > NamenLautDatenbank.txt
cat ../*/teilnehmer_?? | sed 's+*++g' | sort > teilnehmerLautListen.txt


Adressaufkleber fuer den Versand der Dokumentationen
====================================================

K&K benoetigt fuer den Versand der Dokus eine pdf-Datei mit den
Adressen, damit sie direkt die Adressaufkleber bedrucken koennen. Zum
Format hier ein Auszug einer Mail von Angelika Blumer
<kk@copy-druck-service.de>:

  "die Adressaufkleber benötigen als Zweckform Größe ca. 7 x 4 cm
   plaziert auf DIN A4 im Nutzen (21 Adressen) am besten als pdf-
   Datei."

Diesem Format entsprechen recht genau die Zweckform-Aufkleber L7160
(wenngleich K&K auf Aufkleber der Groesse A4 druckt und dann selbst
schneidet). Deswegen habe ich fuer die Adressaufkleber die Groesse der
L7160 Zweckform-Etiketten gewaehlt. K&K ist zufrieden damit.  ;-)

[...]

     Hendrik (20041029)
