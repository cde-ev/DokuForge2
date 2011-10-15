def randstring(n=6):
    """
    @returns: random string of length n
    @type n: int
    @rtype: str
    """
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(sysrand.choice(chars) for x in range(n))
