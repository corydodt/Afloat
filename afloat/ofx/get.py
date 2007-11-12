#!/usr/bin/python
import sys, os
import time
from getpass import getpass
import string
import datetime
from uuid import uuid4

from twisted.python import usage
from twisted.web.client import getPage
from twisted.internet import reactor

from afloat.util import RESOURCE, days


class Options(usage.Options):
    """
    Retrieve OFX events from the server configured in config.py
    """
    synopsis = """get"""
    # optFlags = [[ .. ]]
    # optParameters = [[ .. ]]

    def postOptions(self):
        execfile(RESOURCE('../config.py'), self)
        self['password'] = getpass(
                prompt="Password (%s at %s): " % (self['user'], self['org']),
                stream=sys.stderr)
        
        d = self.doGetting()
        def gotIt(data):
            self['out'] = data
        d.addCallback(gotIt)
        d.addBoth(lambda _: reactor.stop())

        reactor.run()
        print self.get('out', '') + '\n__________________'

    def doGetting(self):
        f = open(RESOURCE('ofx/request.ofx'), 'rb')
        ofx = f.read().strip()
        t = string.Template(ofx)

        dt = datetime.datetime.today()
        dateStart = dt - days(self['lookBehindDays'])

        t = t.substitute({'user': self['user'],
            'time': formatDate14(dt),
            'uuid1': uuid4(),
            'uuid2': uuid4(),
            'uuid3': uuid4(),
            'uuid4': uuid4(),
            'password': self['password'],
            'org': self['org'],
            'fid': self['fid'],
            'accountSavings': self['accountSavings'],
            'accountChecking': self['accountChecking'],
            'encoding': self['encoding'],
            'dateStart': formatDate14(dateStart),
            })

        headers = {'Content-type': 'application/x-ofx'}
        d = getPage(self['url'], headers=headers, method='POST', postdata=t)
        return d


def formatDate14(dt):
    """
    Return a stringified date, YYYYMMDDhhmmss (14 digits)
    """
    return dt.strftime('%Y%m%d%H%M%S')


def run(argv=None):
    if argv is None:
        argv = sys.argv
    o = Options()
    try:
        o.parseOptions(argv[1:])
    except usage.UsageError, e:
        print str(o)
        print str(e)
        return 1

    return 0


if __name__ == '__main__': sys.exit(run())

