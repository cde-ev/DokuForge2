import random
import subprocess

try:
    check_output = subprocess.check_output
except AttributeError:
    def check_output(cmdline):
        proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE)
        output, _ = proc.communicate()
        if proc.returncode:
            raise subprocess.CalledProcessError()
        return output


sysrand = random.SystemRandom()

def randstring(n=6):
    """
    @returns: random string of length n
    @type n: int
    @rtype: str
    """
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(sysrand.choice(chars) for x in range(n))

def strtobool(s):
    """
    @returns: Boolean version of s
    @type s: str
    @rtype: bool
    """
    if s == "True" or s == "true" or s == "t":
        return True
    return False
