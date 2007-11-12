"""
Utility functions
"""
import datetime

from twisted.python.util import sibpath

def RESOURCE(s):
    return sibpath(__file__, s)

def days(amount):
    """
    A simpler timedelta fn
    """
    return datetime.timedelta(days=amount)


