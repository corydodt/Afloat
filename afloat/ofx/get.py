#!/usr/bin/python
import sys, os
import shlex
from getpass import getpass

from twisted.python import usage, procutils
from twisted.internet import reactor, utils

join = str.join

ACCOUNT_CHECKING = 1
ACCOUNT_INVEST = 2
ACCOUNT_CREDIT = 3

def getProcessOutputUtil(commandLine):
    """
    Convenience wrapper around getProcessOutput
    """
    print commandLine
    argv = shlex.split(commandLine)
    executable = procutils.which(argv[0])[0]
    rest = argv[1:]
    env = os.environ
    return utils.getProcessOutput(executable, rest, env, errortoo=True)

class Options(usage.Options):
    synopsis = """get site user [account] [CHECKING/SAVINGS/.. if using BASTMT]
  or
get --listSites
___
"""
    optFlags = [['listSites', 'l', 'List all available bank sites']]
    optParameters = [['outdir', 'd', '.', 
        'Directory to put output files (statement.ofx, account.ofx)'],
        ]

    def parseArgs(self, siteName=None, user=None, account=None, accountType=None):
        if self['listSites']:
            return

        # manually check that args were supplied, so we can have
        # the special listSites behavior without causing a UsageError.
        if None in (siteName, user, account, accountType):
            raise usage.UsageError("Wrong number of arguments :(")

        self['siteName'] = siteName
        self['user'] = user
        self['account'] = account
        self['accountType'] = accountType

    def opt_listSites(self):
        raise NotImplemented
        print "AVAILABLE SITES:\n", joined
        self['listSites'] = True

    def postOptions(self):
        if self['listSites']:
            return

        import afloat.ofx.get
        siteClass = getattr(afloat.ofx.get, self['siteName'], None)
        if siteClass is not None:
            self['site'] = siteClass
        else:
            raise usage.UsageError(
                    "** That is not a site I know. Try --listSites")

        
        d = self.doGetting()
        d.addBoth(lambda _: reactor.stop())

        reactor.run()

    def doGetting(self):
        site = self['site']
        account = self['account']
        acType = self['accountType']
        user = self['user']

        passwd = getpass(prompt="Password (%s at %s): " % (user, site.org))

        command1 = accountInfoCommand(self['user'], passwd, site, self['outdir'])
        d1 = getProcessOutputUtil(command1)

        command2 = statementCommand(self['user'], passwd, site, self['outdir'],
                account, acType)
        d1.addCallback(lambda _: getProcessOutputUtil(command2))

        return d1


class EECU(object):
    fid = "321172594"
    bank = "321172594"
    url = "https://www.eecuonline.org/scripts/isaofx.dll"
    org = "Educational Employees C U"
    

def accountInfoCommand(user, password, bank, outdir):
    c = '''ofxconnect -a --user=%(user)s --pass="%(pass)s" --fid=%(fid)s 
        --bank=%(bank)s --org="%(org)s" --url=%(url)s
        "%(outdir)s"/account.ofx'''
    d = bank.__dict__.copy()
    d.update( {'user': user, 'pass': password, 'outdir': outdir} )
    c = c % d
    return c


def statementCommand(user, password, bank, outdir, account, accountType):
    c = '''ofxconnect -s --user=%(user)s --pass="%(pass)s" --fid=%(fid)s 
        --bank=%(bank)s --org="%(org)s" --acct=%(account)s 
        --type=%(accountType)s --past=30 --url=%(url)s
        %(outdir)s/statement.ofx'''
    d = bank.__dict__.copy()
    d.update( {'user': user, 'pass': password, 'account': account,
        'accountType': accountType, 'outdir': outdir})
    c = c % d
    return c


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

