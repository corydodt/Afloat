#!/usr/bin/python
import sys, os
import shlex
import time
from getpass import getpass
import string

from twisted.python import usage, procutils
from twisted.web.client import getPage
from twisted.internet import reactor, protocol, defer

from afloat.util import RESOURCE


def spawnProcessUtil(processProtocol, commandLine):
    """
    Convenience wrapper around spawnProcess
    """
    print commandLine
    argv = shlex.split(commandLine)
    executable = procutils.which(argv[0])[0]
    rest = argv[1:]
    env = os.environ
    return reactor.spawnProcess(processProtocol, executable, rest, env,
            usePTY=1)


class CurlProtocol(protocol.ProcessProtocol):
    def __init__(self, processDeferred, *a, **kw):
        self.processDeferred = processDeferred
        self.data = []

    def errReceived(self, data):
        print data,

    def outReceived(self, data):
        self.data.append(data)

    def processEnded(self, reason):
        self.processDeferred.callback(''.join(self.data))


class Options(usage.Options):
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

        dt = time.strftime('%Y%m%d%H%M%S')

        getuuid = lambda: os.popen('/usr/bin/uuidgen').read().strip()
        uuid1 = getuuid()
        uuid2 = getuuid()
        uuid3 = getuuid()
        uuid4 = getuuid()

        t = t.substitute({'user': self['user'],
            'time': dt,
            'uuid1': uuid1,
            'uuid2': uuid2,
            'uuid3': uuid3,
            'uuid4': uuid4,
            'password': self['password'],
            'org': self['org'],
            'fid': self['fid'],
            'accountSavings': self['accountSavings'],
            'accountChecking': self['accountChecking'],
            'encoding': self['encoding'],
            })

        headers = {'Content-type': 'application/x-ofx'}
        d = getPage(self['url'], headers=headers, method='POST', postdata=t)
        # d = defer.Deferred()
        # pp = CurlProtocol(d, t)
        # ## cmd = 'curl --data-binary "%s" -H "Connection: close" -H "Content-Type: application/x-ofx" %s' % (self['url'],)
        # ## spawnProcessUtil(pp, cmd)
        # reactor.spawnProcess(pp, '/usr/bin/curl', ['--data-binary', t, '-H',
        #     'Connection: close', '-H', 'Content-type:application/x-ofx',
        #     self['url']], env=os.environ)
        return d


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

