# vi:ft=python
import sys, os
import string
import getpass
import time

from twisted.python import usage


class Options(usage.Options):
    synopsis = "formatofxreq input.ofx.in configFile"
    def parseArgs(self, filename, configFile):
        self['filename'] = filename
        execfile(configFile, self)

    def postOptions(self):
        f = open(self['filename'], 'rb')
        ofx = f.read().strip()
        t = string.Template(ofx)

        password = getpass.getpass('Your bank password: ', stream=sys.stderr)
        dt = time.strftime('%Y%m%d%H%M%S')

        getuuid = lambda: os.popen('/usr/bin/uuidgen').read().strip()
        uuid1 = getuuid()
        uuid2 = getuuid()
        uuid3 = getuuid()
        uuid4 = getuuid()

        print t.substitute({'user': self['user'],
            'time': dt,
            'uuid1': uuid1,
            'uuid2': uuid2,
            'uuid3': uuid3,
            'uuid4': uuid4,
            'password': password,
            'org': self['org'],
            'fid': self['fid'],
            'accountSavings': self['accountSavings'],
            'accountChecking': self['accountChecking'],
            })





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
