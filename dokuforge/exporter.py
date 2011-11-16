import tempfile
import string
import re

def testCourseName(course):
    if re.match('^kurs[0-9]+$', course.name) is None:
        return False
    return True

def courseNumber(course):
    return course.name[4:]

## do template substitiution
def tsubst(template, **keys):
    return string.Template(template.safe_substitute(keys))

class Exporter:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="export")
        self.exported = False
        self.template_course = r"""\course{${COURSENUMBER}}

${COURSECONTENT}

\endinput
"""
        self.template_coursepage = r"""${COU

    def export(self, aca):
        if self.exported:
            return False
        self.exported = True
        self.aca = aca
        courses = self.aca.listCourses()
        courses = filter(testCourseName, courses)
        for c in courses:
            template = string.Template(self.template_course)
            template = tsubst(template, COURSENUMBER = courseNumber(course))
            for p in c.listpages():
                
