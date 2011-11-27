# -*- coding: utf-8 -*-
import tempfile
import string
import re
import os
import shutil
import errno

from dokuforge.exportparser import DokuforgeToTeXParser
from dokuforge.common import check_output

## Templates used for generating the export

template_course = ur"""\course{${COURSENUMBER}}
${COURSECONTENT}
\endinput
"""

template_coursepage = ur"""${COURSEPAGE}
${PAGEFIGURES}
${COURSECONTENT}"""

template_master = ur"""\documentclass{padoc}
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

""" + u'\\' + ur"""usepackage[colorlinks=true,linkcolor=black,citecolor=black,urlcolor=black]{hyperref}

""" + u'\\' + ur"""usepackage{mathalign}
""" + u'\\' + ur"""usepackage{amsmath}
""" + u'\\' + ur"""usepackage{misc}
""" + u'\\' + ur"""usepackage{multicol}

\begin{document}

\include{fortschritt}

\include{titel}
\include{vorwort}

\tableofcontents
${COURSELIST}
\end{document}
"""

template_figure = ur"""\begin{figure}
  \centering
  \includegraphics[width=.6\textwidth]{${FIGUREPATH}}
  \caption{${FIGURECAPTION}}
  \label{${FIGURELABEL}}
\end{figure}
${PAGEFIGURES}
"""

template_fortschritt = ur"""\begin{ednote}
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

template_coursenotes = ur"""Kurs ${COURSENUMBER} (${COURSETITLE})
Verantwortlich:
[ ] Redaktion  [ ] Bilder/Grafiken

${COURSENOTES}"""

## end of templates

def testCourseName(course):
    """
    Filter for course names.

    padoc.cls expects a certain format for course names.
    @rtype: bool
    @returns: True if the course name is compatible with padoc.cls
    """
    if re.match('^kurs[0-9]+$', course.name) is None:
        return False
    return True

def courseNumber(course):
    """
    Extract the course number from a course name.

    This works in conjunction with testCourseNames, which allows only a very
    limited set of course names.
    """
    return course.name[4:]

def tsubst(template, **keys):
    """
    Helper function for template substitution.
    """
    return string.Template(template.safe_substitute(keys))

def writefile(path, content):
    """
    Helper function for writing files.
    """
    f = file(path, mode = "w")
    f.write(content)
    f.close()

class Exporter:
    """
    Exporter class.

    Take an academy and build transform it into a (rather complex)
    TeX-document. Bundle everything up and provide a tar-ball. Most of the
    magic is in the exportparser, the other steps are pretty
    straight-forward.

    Everything happens inside a temporary directory which is deleted
    afterwards. Also note, that all files under 'exporter-files' are copied
    to the output.
    """
    def __init__(self, aca):
        """
        Prepare for the export.
        """
        self.tempdir = tempfile.mkdtemp(prefix="export")
        os.mkdir(os.path.join(self.tempdir, "%s" % aca.name))
        self.dir = os.path.join(self.tempdir, "%s" % aca.name)
        self.exported = False
        self.aca = aca

    def export(self):
        """
        Export.

        @returns: bzipped tar-ball with the export or None (if allready exported)
        """
        if self.exported:
            return None
        self.exported = True
        courses = self.aca.listCourses()
        ## we have to filter the courses, so all course names conform with
        ## padoc.cls
        courses = filter(testCourseName, courses)
        ## the listing of courses inside master.tex
        courselist = u'\n'
        ## the listing of courses inside fortschritt.tex
        fortschrittlist = string.Template(u'${COURSENOTES}')
        ## export one course
        for c in courses:
            ## each course gets it's own directory
            os.mkdir(os.path.join(self.dir, c.name))
            ## content is later written to chap<coursenumber>.tex
            content = string.Template(template_course)
            content = tsubst(content, COURSENUMBER = courseNumber(c))
            for p in c.listpages():
                content = tsubst(content, COURSECONTENT = template_coursepage)
                ## here be dragons
                parser = DokuforgeToTeXParser(c.showpage(p))
                parser.parse()
                content = tsubst(content, COURSEPAGE = parser.result())
                for b in c.listblobs(p):
                    blob = c.viewblob(b)
                    content = tsubst(content, PAGEFIGURES = template_figure)
                    content = tsubst(content,
                                     FIGUREPATH = os.path.join(c.name,
                                                               blob["filename"]),
                                     FIGURELABEL = blob["label"],
                                     FIGURECAPTION = blob["comment"])
                    ## filenames are trusted
                    writefile(os.path.join(self.dir, c.name, blob["filename"]),
                              blob["data"])
                content = tsubst(content, PAGEFIGURES = u'')
            content = tsubst(content, COURSECONTENT = u'')
            content = content.safe_substitute()
            writefile(os.path.join(self.dir, c.name,
                                  "chap%s.tex" % courseNumber(c)), content)
            ## update lists
            courselist += u'\\include{%s/chap%s.tex}\n' % (c.name, courseNumber(c))
            fortschrittlist = tsubst(fortschrittlist,
                                     COURSENOTES = template_coursenotes)
            fortschrittlist = tsubst(fortschrittlist,
                                     COURSENUMBER = courseNumber(c),
                                     COURSETITLE = c.gettitle())
        ## create fortschritt.tex
        fortschrittlist = tsubst(fortschrittlist, COURSENOTES = u'')
        fortschrittlist = fortschrittlist.safe_substitute()
        fortschritt = string.Template(template_fortschritt)
        fortschritt = tsubst(fortschritt, COURSENOTES = fortschrittlist)
        fortschritt = fortschritt.safe_substitute()
        writefile(os.path.join(self.dir, "fortschritt.tex"), fortschritt)
        ## create master.tex
        master = string.Template(template_master)
        master = tsubst(master, COURSELIST = courselist)
        master = master.safe_substitute()
        writefile(os.path.join(self.dir, "master.tex"), master)
        ## copy exporter-files/*
        for f in os.listdir(os.path.join(os.path.dirname(__file__),
                                         "exporter-files")):
            ## this is a bit tedious since we copy directory and files
            try:
                shutil.copytree(os.path.join(os.path.dirname(__file__),
                                             "exporter-files", f),
                                             os.path.join(self.dir, f))
            except OSError as exception:
                if exception.errno == errno.ENOTDIR:
                    shutil.copy(os.path.join(os.path.dirname(__file__),
                                             "exporter-files", f), self.dir)
                else:
                    raise
        ## bundle up
        data = check_output(["tar", "cjf", "-", "-C", self.tempdir, self.aca.name])
        ## clean up
        shutil.rmtree(self.tempdir)
        return data

