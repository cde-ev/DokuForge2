# Copyright (c) 2012, Klaus Aehlig, Helmut Grohne, Markus Oehme
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the three-clause BSD license.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# You should have received a copy of the Three-Clause BSD License
# along with this program in the file COPYING.
# If not, see <http://opensource.org/licenses/bsd-3-clause>
from collections import Mapping

class LazyView(Mapping):
    """A lazy way to write the following expression.::

         dict((key, function()) for key, function in functions.items())

    In this case lazy means that the functions are only called when the values
    are actually requested and in addition the returned values are cached. An
    additional difference to normal dicts is that attemping to write to a
    LazyView will fail with a TypeError (as defined by collections.Mapping).
    """
    def __init__(self, functions):
        """
        @type functions: {key: callable}
        @param functions: from arbitrary keys to parameterless functions
        """
        self._functions = functions
        self._values = dict()

    def __len__(self):
        return len(self._functions)

    def __iter__(self):
        return iter(self._functions)

    def __getitem__(self, key):
        """Looks up the given key. If a value is already present, it is
        returned. Otherwise, it is computed by calling the corresponding
        function and caching its result.
        @raises KeyError: if there is no function associated with the key
        @note: This can raise pretty much any exception since we are calling
               user defined functions.
        """
        try:
            return self._values[key]
        except KeyError:
            value = self._functions[key]()
            self._values[key] = value
            return value

def liftdecodeutf8(fun):
    """
    @returns: a function returning fun().decode("utf8")
    @rtype: () -> unicode
    """
    return lambda:fun().decode("utf8")
