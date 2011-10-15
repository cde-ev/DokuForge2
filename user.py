import random
import string

sysrand = random.SystemRandom()

from common import *

def randpasswordstring(n=6):
    """
    @returns: random string of length n which is easily readable
    @type n: int
    @rtype: str
    """
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz123456789'
    return ''.join(sysrand.choice(chars) for x in range(n))


class User:
    """
    User-Class

    ...
    """
    def __init__(self, name, status, password, permissions):
        """
        User-Class Constructor

        ...
        """
        self.name = name
        self.status = status
        if password == "":
            password = randpasswordstring(6)
        self.password = password
        self.permissions = permissions

class UserDB:
    def __init__(self):
        self.db = dict()
    def addUser(self, name, status, password, permissions):
        if name in self.db:
            return False
        self.db[name] = User(name, status, password, permissions)
        return True
    def modifyUser(self, name, attributes):
        if not name in self.db:
            return False
        for (attr_name, attr_value) in attributes:
            if attr_name == "status":
                self.db[name].status = attr_value
            elif attr_name == "password":
                self.db[name].password = attr_value
            elif attr_name == "permission_grant":
                self.db[name].permissions[attr_value] = True
            elif attr_name == "permission_revoke":
                self.db[name].permissions[attr_value] = False
            else:
                print "Unknown attribute", attr_name, "w/ value", attr_value
    def hasPermission(self, name, perm):
        if not name in self.db:
            return False
        if not perm in self.db[name].permissions:
            return False
        if self.db[name].permissions[perm]:
            return True
        return False
    def checkLogin(self, name, password):
        """
        @type name: str
        @type passwordn: str
        @returns: True if name and password match an existing user, False otherwise
        """
        if not name in self.db:
            return False
        if self.db[name].password == password:
            return True
        return False



