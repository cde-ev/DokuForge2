#!/usr/bin/env python

from dokuforge.parser import dfLineGroupParser
import random

def testParser():
    for i in range(100):
        for l in range(10, 100):
            inp = "".join(random.choice("aA \n*[()]1.$\\-") for _ in range(l))
            inp2 = dfLineGroupParser(inp).toDF()
            inp3 = dfLineGroupParser(inp2).toDF()
            if inp2 != inp3:
                print("parser not idempotent on input: %r" % inp)
                return False
    return True

if __name__ == '__main__':
    random.seed(0) # Reproducible tests!
    print "Testing idempotency of toDF o parse..."
    if not testParser():
        exit(1)
    print "OK"
    
