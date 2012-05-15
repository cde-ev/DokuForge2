from dokuforge.parser import dfLineGroupParser

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


if __name__ == "__main__":
    print time("[foobar]", "test case")
