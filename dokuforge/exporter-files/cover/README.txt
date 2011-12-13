uebersetzen mit latex (nicht pdflatex), d. h. Logo muss als eps vorliegen
konvertieren sollte so gehen:
gs -q -dNOPAUSE -dBATCH -dSAFER -sDEVICE=epswrite -sOutputFile=logo.eps -c save pop -f logo.pdf

anschliessend dvipdf