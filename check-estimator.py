#!/usr/bin/env python

import sys
import os.path
import math
from dokuforge.course import Course
from dokuforge.parser import Estimate

class Case:
    def __init__(self, academy, course, length, fitness, correction):
        self.academy = academy
        self.course = course
        self.length = length
        self.fitness = fitness
        self.correction = correction
        self.estimate = None

def process_case(case, df2path):
    course = Course(os.path.join(df2path, case.academy, case.course))
    estimate = Estimate.fromNothing()
    for outline in course.outlinepages():
        estimate += outline.estimate
    # maybe we should incorporate ednotes, but that's pretty hairy
    return estimate.pages + estimate.blobpages

def make_statistics(cases):
    factors = []
    for case in cases:
        factors.append(case.estimate / (case.length + case.correction))
    mean = sum(factors)/len(factors)
    stddev = math.sqrt(sum(x*x - mean for x in factors)/len(factors))
    print("== detailed results ==")
    for case, factor in zip(cases, factors):
        sign = '+'
        if case.correction < 0:
            sign = '-'
        print("{}/{}: actual: {}{}{} estimated: {} factor: {}".format(
            case.academy, case.course, case.length, sign, abs(case.correction),
            case.estimate, factor))
    splitpoints = [.67, .8, .9, .95, 1.05, 1.1, 1.2, 1.5]
    buckets = [0] * (len(splitpoints) + 1)
    for factor in factors:
        test = [factor > point for point in splitpoints]
        buckets[test.count(True)] += 1
    print("== overall statistics ==")
    print("Mean: {}".format(mean))
    print("Standard Deviation: {}".format(stddev))
    lower = ["-infty"] + splitpoints
    upper = splitpoints + ["+infty"]
    bucketoutput = ", ".join("({}, {}) : {}".format(l,u, b) for l, u, b in zip(lower, upper, buckets))
    print("Buckets of distribution: {}".format(bucketoutput))
    
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
"""Usage: check-estimator /path/to/data fitness-level /path/to/df2dir
    where fitness-level is an integer from 0 to 5
    according to the following table).

    0: wrong data (possibly not texed yet)
    1: no chance for estimator to get it right
    2: difficult to estimate
    3: reasonaby estimatable
    4: perfect test case

    The data file has as pipe-separated values in an org-mode table the entries
    academy: name of academy
    course: name of course
    length: actual length in print
    fitness: see above
    correction: correct for obvious deviations (like extra images)
""")
        exit(1)
    inputdata = []
    with open(sys.argv[1]) as f:
        # pop the header
        f.readline()
        f.readline()
        for line in f:
            csv = line.split('|')[1:-1]
            if not csv:
                continue
            csv[0] = csv[0].strip()
            csv[1] = csv[1].strip()
            csv[2] = float(csv[2])
            csv[3] = int(csv[3])
            csv[4] = float(csv[4])
            inputdata.append(Case(*csv))
    cases = []
    fitness_cutoff = int(sys.argv[2])
    for case in inputdata:
        if case.fitness >= fitness_cutoff:
            case.estimate = process_case(case, sys.argv[3])
            cases.append(case)
    make_statistics(cases)
    print("Considered {} cases with fitness at least {} out of {} available cases".format(
        len(cases), fitness_cutoff, len(inputdata)))
