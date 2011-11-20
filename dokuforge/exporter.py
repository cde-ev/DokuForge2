import tempfile
import string
import re
import os
import subprocess

from dokuforge.exportparser import DokuforgeToTeXParser

template_course = r"""\course{${COURSENUMBER}}
${COURSECONTENT}
\endinput
"""

template_coursepage = r"""${COURSEPAGE}
${COURSECONTENT}"""

template_master = r"""\documentclass{padoc}
\listfiles

\makeatletter

\def\ednote%
  {\@verbatim\frenchspacing\@vobeyspaces\@xednote}
\def\endednote%
  {\if@newlist \leavevmode\fi\endtrivlist}
\begingroup
  \catcode `[= 1 \catcode`]=2
  \catcode `\{=12 \catcode `\}=12
  \catcode `|=0 \catcode`\\=12
  |gdef|@xednote#1\end{ednote}[#1|end[ednote]]
|endgroup

\let\b@ckslash\backslash
\def\backslash%
  {\ifmmode\b@ckslash\else$\b@ckslash$\fi}

\makeatother

\let\@\empty
\let\acronym\textsmaller

%% Pakete und Definitionen

\usepackage[colorlinks=true,linkcolor=black,citecolor=black,urlcolor=black]{hyperref}

\usepackage{mathalign}
\usepackage{amsmath}
\usepackage{misc}
\usepackage{multicol}

\begin{document}

\include{fortschritt}

\include{titel}
\include{vorwort}

\tableofcontents
${COURSELIST}
\end{document}
"""

template_figure = r"""\begin{figure}
  \centering
  \includegraphics[width=.6\textwidth]{${FIGUREPATH}}
  \caption{${FIGURECAPTION}}
  \label{${FIGURELABEL}}
\end{figure}
"""

template_fortschritt = r"""\begin{ednote}
${COURSENOTES}Allgemeines:
[ ] Kursfotos nachbearbeiten: 
[ ] Orga-/Gesamtfotos nachbearbeiten:  
[ ] Namenslisten-Abgleich Datenbank
[ ] Namenslisten: KL kennzeichnen: 
[ ] Vorwort
[ ] Titelseite (Logo, Text)
[ ] Fuellbilder
[ ] Fotos druckbar

Bitte Namen fuer die Redaktion eintragen und, wenn fertig, 
durch Ankreuzen abhaken.
\end{ednote}
"""

template_coursenotes = r"""Kurs ${COURSENUMBER} (${COURSETITLE})
Verantwortlich:
[ ] Redaktion  [ ] Bilder/Grafiken

${COURSENOTES}"""

def testCourseName(course):
    if re.match('^kurs[0-9]+$', course.name) is None:
        return False
    return True

def courseNumber(course):
    return course.name[4:]

## do template substitiution
def tsubst(template, **keys):
    return string.Template(template.safe_substitute(keys))

def writefile(path, content):
    f = file(path, mode = "w")
    f.write(content)
    f.close()

class Exporter:
    def __init__(self, aca):
        self.dir = tempfile.mkdtemp(prefix="export")
        self.exported = False
        self.aca = aca

    def export(self):
        if self.exported:
            return False
        self.exported = True
        courses = self.aca.listCourses()
        courses = filter(testCourseName, courses)
        courselist = u'\n'
        fortschrittlist = string.Template(u'${COURSENOTES}')
        for c in courses:
            os.mkdir(os.path.join(self.dir, c.name))
            content = string.Template(template_course)
            content = tsubst(content, COURSENUMBER = courseNumber(c))
            for p in c.listpages():
                content = tsubst(content, COURSECONTENT = template_coursepage)
                parser = DokuforgeToTeXParser(c.showpage(p))
                parser.parse()
                content = tsubst(content, COURSEPAGE = parser.result())
            content = tsubst(content, COURSECONTENT = u'')
            content = content.safe_substitute()
            writefile(os.path.join(self.dir, c.name,
                                  "chap%s.tex" % courseNumber(c)), content)
            courselist += u'\\include{%s/chap%s.tex}\n' % (c.name, courseNumber(c))
            fortschrittlist = tsubst(fortschrittlist,
                                     COURSENOTES = template_coursenotes)
            fortschrittlist = tsubst(fortschrittlist,
                                     COURSENUMBER = courseNumber(c),
                                     COURSETITLE = c.gettitle())
        fortschrittlist = tsubst(fortschrittlist, COURSENOTES = u'')
        fortschrittlist = fortschrittlist.safe_substitute()
        fortschritt = string.Template(template_fortschritt)
        fortschritt = tsubst(fortschritt, COURSENOTES = fortschrittlist)
        fortschritt = fortschritt.safe_substitute()
        writefile(os.path.join(self.dir, "fortschritt.tex"), fortschritt)
        master = string.Template(template_master)
        master = tsubst(master, COURSELIST = courselist)
        master = master.safe_substitute()
        writefile(os.path.join(self.dir, "master.tex"), master)
        for f in os.listdir(os.path.join(os.path.dirname(__file__), "exporter-files")):
            subprocess.check_call(["cp", "-r", "-t", self.dir, os.path.join(os.path.dirname(__file__), "exporter-files", f)], cwd=os.path.dirname(__file__))
