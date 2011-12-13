#! /usr/bin/env python

import sys, os, csv

POS = [[27, 0,22,14, 0],   # Deutsche Adresse
       [27,22,17, 9, 0],   # Deutsche Adresse mit Adresszusatz
       [31, 0,26,18,10],   # Auslaendische Adresse
       [31,26,21,13, 5],   # Auslaendische Adresse mit Adresszusatz
      ]

reader = csv.reader(open("adressen.csv", "rb"), delimiter=';')

out = open('adressen.tex', 'w')

out.write('\\documentclass[a4paper,10pt]{letter}\n\n')
out.write('\\usepackage[zwl7160]{ticket}\n')
out.write('\\usepackage[utf8]{inputenc}\n')
out.write('\\renewcommand{\sfdefault}{uop}\n')
out.write('\\renewcommand{\\ticketdefault}{}\n\n')
out.write('\\begin{document}\n')
out.write('\\sffamily\n')

AdressenInland = []
AdressenAusland = []

for row in reader:
    name    = row[2] + ' ' + row[3]
    street1 = row[6]
    street2 = row[7]
    town    = (row[8] + ' ' + row[9]).strip()
    country = row[10]
    print ( name );
    if ( country == '' ):
        AdressenInland.append ( ( row[8], name, street1, street2, town ) ) # erster Eintrag: PLZ, danach wird sortiert
    if ( country != '' ):
        AdressenAusland.append ( ( row[10], name, street1, street2, town, country ) ) # hier wird nach Land sortiert
        
AdressenInland.sort();
AdressenAusland.sort();

for i in range ( len(AdressenAusland) ):
    pos = 2
    if (AdressenAusland[i][2] != ''): pos += 1

    out.write('\\ticket{\n')
    out.write('  \\put( 7, %d){\\small %s}\n' %(POS[pos][0],AdressenAusland[i][1]))
    if (AdressenAusland[i][2] != ''):
        out.write('  \\put( 7, %d){\\small %s}\n' %(POS[pos][1],AdressenAusland[i][2]))
    out.write('  \\put( 7, %d){\\small %s}\n' %(POS[pos][2],AdressenAusland[i][3]))
    out.write('  \\put( 7, %d){\\small %s}\n' %(POS[pos][3],AdressenAusland[i][4]))
    out.write('  \\put( 7, %d){\\small \\textbf{%s}}\n' %(POS[pos][4],AdressenAusland[i][5]))
    out.write('}\n')

for i in range ( len(AdressenInland) ):
    pos = 0
    if (AdressenInland[i][2] != ''): pos += 1

    out.write('\\ticket{\n')
    out.write('  \\put( 7, %d){\\small %s}\n' %(POS[pos][0],AdressenInland[i][1]))
    if (AdressenInland[i][2] != ''):
        out.write('  \\put( 7, %d){\\small %s}\n' %(POS[pos][1],AdressenInland[i][2]))
    out.write('  \\put( 7, %d){\\small %s}\n' %(POS[pos][2],AdressenInland[i][3]))
    out.write('  \\put( 7, %d){\\small %s}\n' %(POS[pos][3],AdressenInland[i][4]))
    out.write('}\n')

out.write('\\end{document}\n')
out.close()

