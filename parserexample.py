#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dokuforge.parser import dfLineGroupParser

teststring = u"""
[Eine Ueberschrift]
[[Eine Unterueberschrift]]
(Autor, Korrektor und Chef)

 Lorem  囲碁  ipsum dolor sit amet, consectetur adipiscing elit. Nullam vel dui
mi. Mauris feugiat erat eget quam varius eu congue lectus viverra. Ut sed
  velit dapibus eros ultricies blandit a in felis. Nam ultricies pharetra
luctus. Nam aliquam lobortis rutrum. Phasellus quis arcu non dui pretium
  aliquam. Phasellus id mauris mauris, quis lobortis justo.

[Eine zweite Ueberschrift]
 [[Keine Unterueberschrift]]
(Kein Autor)

Fermats letzter Satz sagt, dass die Gleichung $x^n+y^n = z^n$ fuer $n\\ge3$
keine ganzzahlige Loesung, auszer den trivialen, besitzt. Dies war ein
_lange_ Zeit unbewiesenes Theorem. Hier nun eine Liste von interessanten
Zahlen. Diese Formel steht $$e^{i\\pi}+1=0$$ im Text ist aber eigentlich abgesetzt.

$$\\binom{n}{k}+\\binom{n}{k+1}=\\binom{n+1}{k+1}$$

Aber *NullKeinSchalgwort* war lange Zeit gar keine Zahl. Nam ultricies pharetra
luctus. Nam aliquam lobortis rutrum. Phasellus quis arcu non dui pretium
aliquam. Phasellus id mauris mauris, quis lobortis justo.

*ZweiundvierzigSchlagwort* ist eine Zahl die als Antwort sehr beliebt ist. Nullam eget
tortor ipsum, in rhoncus mi. Sed nec odio sem. Aenean rutrum, dui vel
vehicula pulvinar, purus magna euismod dui, id pharetra o.Ä. libero mauris nec
dolor.

Bitte Escape mich: <>&"'\\ und das wars auch schon.

[[Eine weitere Unterueberschrift]]

(kein Autor)

Wir packen unsere Koffer und nehmen mit
- einen Sonnenschirm, Kapazitaet 3000000 kWh was eine sehr grosze Zahl ist,
    aber zum Glueck noch auf diesen Absatz passt
- Wanderschuhe, Fassungsvermoegen 2 l
- Huepfeseil, Laenge 1 m$^2$
- Plueschkrokodil, Flauschigkeit 79%

Dies schreiben wir auf den Seiten 5--7 in die Tabelle. Dabei geht es --
anders als in so mancher andrer Uebung -- nicht ums blosze wiederholen. Und
so sagte schon Goethe "auch aus Steinen die einem in den Weg gelegt werden,
kann man schoenes bauen", wollen wir uns also ein Beispiel nehmen. Und jetzt
machen wir noch einen Gedankensprung -- schon sind wir auf einem anderen
Planeten.

_Man_ kann z.B. auch ganz viele Abkuerzungen u.a. unterbringen um lange
Absaetze (s.o.) zu stutzen, aber das ist nur ca. halb so leserlich. Auch
nicht besser wird es wenn man ganz viele AKRONYME verwendet ... Aber
manchmal kann es auch nuetzlich sein, so bei ABBILDUNG:zwei gesehen.

{ Hier noch ein Hinweis in verbatim,

  mit einer Leerzeile. }

{
 Und hier sehen wir, das { nested braces } auch gehen sind.
 Dabei duerfen sie wie jetzt } nicht am Zeilenende stehen.
}

Normaler Text.

{[( special ednote }
    immer noch
)]}

Und wieder ganz normaler Text.
"""

parsed = dfLineGroupParser(teststring);

print parsed.debug()

print "========================================"

print parsed.toDF().encode("utf8")

print "========================================"

print parsed.toHtml().encode("utf8")

print "========================================"

print parsed.toTex().encode("utf8")

print "========================================"

print parsed.toEstimate()

