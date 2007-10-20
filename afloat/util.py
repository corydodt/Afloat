"""
Utility functions
"""

from twisted.python.util import sibpath

def RESOURCE(s):
    return sibpath(__file__, s)
