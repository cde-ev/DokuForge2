from dokuforge.parser import dfLineGroupParser
from dokuforge.storagedir import StorageDir
from dokuforge.course import Course

import os
import timeit

def time(text, id, number=100):
    """
    Compute the time the parser needs on text and return the tripple
    (time, length, id) where time is the runtime for a single call in
    seconds, and length is the length of the text.
    """
    values = timeit.repeat(lambda: dfLineGroupParser(text), number=number, repeat=10)
    time = min(values) / (1.0 * number)
    print "DDD %4.0fms %d %s" % (time * 1000, len(text), id)
    return (time, len(text), id)

def timecourse(dirname):
    values = []
    course = Course(StorageDir(dirname))
    pages = course.listpages()
    for page in pages:
        s = course.showpage(page)
        values.append(time(s, "%s-%d" % (dirname, page)))
    return values
        
def timeacademy(dirname):
    values = []
    coursedirs = (os.path.join(dirname, entry)
                  for entry in os.listdir(dirname))
    coursedirs = filter(os.path.isdir, coursedirs)
    for coursedir in coursedirs:
        values.extend(timecourse(coursedir))
    return values

if __name__ == "__main__":
    results = timeacademy("/tmp/wa2012-1/")
    print
    print
    results.sort()
    print results
