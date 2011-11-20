import tempfile
import string
import re
import os

from dokuforge.exportparser import DokuforgeToTeXParser

template_course = r"""\course{${COURSENUMBER}}

${COURSECONTENT}

\endinput
"""

template_coursepage = r"""${COURSEPAGE}

${COURSECONTENT}
"""

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

template_course

def testCourseName(course):
    if re.match('^kurs[0-9]+$', course.name) is None:
        return False
    return True

def courseNumber(course):
    return course.name[4:]

## do template substitiution
def tsubst(template, **keys):
    return string.Template(template.safe_substitute(keys))

def postprocessor(data):
    ## compress excessive newlines
    while '\n\n\n' in data:
        data = data.replace('\n\n\n', '\n\n')
    return data


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
        for c in courses:
            os.mkdir(os.path.join(self.dir, c.name))
            f = file(os.path.join(self.dir, c.name,
                                  "chap%s.tex" % courseNumber(c)), mode = "w")
            content = string.Template(template_course)
            content = tsubst(content, COURSENUMBER = courseNumber(c))
            for p in c.listpages():
                content = tsubst(content, COURSECONTENT = template_coursepage)
                parser = DokuforgeToTeXParser(c.showpage(p))
                parser.parse()
                content = tsubst(content, COURSEPAGE = parser.result())
            content = tsubst(content, COURSECONTENT = u'')
            content = content.safe_substitute()
            f.write(postprocessor(content))
