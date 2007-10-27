# vi:ft=python
import sys

from twisted.python import usage

import sgmllib


class Banking(object):
    """
    Your set of accounts, and the server date of the calls we made
    """
    def __init__(self):
        self.accounts = {}

    def addAccount(self, account):
        self.accounts[account.id] = account

    def getAccount(self, id):
        return self.accounts[id]


class Account(object):
    """
    A single account, with all your transactions
    """
    def __init__(self):
        self.transactions = {}

    def addTransaction(self, txn):
        self.transactions[txn.id] = txn


class Transaction(object):
    """
    One transaction (date, memo, checknum, amount)
    """
    def __init__(self):
        pass


class OFXParser(sgmllib.SGMLParser):
    """
    Get financials out.  We need (from signon, acctlist, bankstmt):
.      /ofx/signonmsgsrsv1/dtserver
.                         /fi/fid (to verify)
_                         /users.primacn (to verify)
_          /signupmsgsrsv1/acctinfors/acctinfo/bankacctinfo/bankacctfrom/acctid (all available, key)
_                                                          /users.bankinfo/ledgerbal/balamt (all by acctid)
_                                                                         /availbal/balamt (all by acctid)
_                                                                         /hold/dtapplied (all by acctid, key)
_                                                                              /desc  (all by acctid by dtapplied)
_                                                                              /amt  (all by acctid by dtapplied)
_                                                                         /regdcnt (all by accountid)
_                                                                         /regdmax (all by accountid)
_          /bankmsgsrsv1/stmtrnsrs/stmtrs/bankacctfrom/acctid (to verify)
_                                        /banktranlist/stmttrn/fitid (all available, key)
_                                                             /trntype
_                                                             /trnamt
_                                                             /dtposted
_                                                             /dtuser
_                                                             /memo
_                                                             /checknum
_                                                             /users.stmt/trnbal (to verify)
_                                        /ledgerbal/balamt (assert against signup ledgerbal)
_                                        /availbal/balamt (assert against signup ledgerbal)
    """

    ## def finish_starttag(self, tag, attrs):
    ##     """
    ##     In my subclass, replace "." with "_" in tagnames
    ##     """
    ##     tag = tag.replace('.', '_')
    ##     return sgmllib.SGMLParser.finish_starttag(self, tag, attrs)

    ## def finish_endtag(self, tag, ):
    ##     """
    ##     In my subclass, replace "." with "_" in tagnames
    ##     """
    ##     tag = tag.replace('.', '_')
    ##     return sgmllib.SGMLParser.finish_endtag(self, tag, )

    def __init__(self, *a, **kw):
        sgmllib.SGMLParser.__init__(self, *a, **kw)
        self._data = ""
        self._stateStack = []
        self.banking = Banking()
        self.currentAccount = None
        self.currentTransaction = None

    def handle_data(self, data):
        if data.strip() and self._stateStack:
            self._data = self._data + data
            if self._stateStack[-1] != '#CDATA':
                self._stateStack.append('#CDATA')

    def unknownData(self, stack, tag, data):
        print '  ' * len(self._stateStack) + '    #CDATA'

    def implicitClose(self):
        """Handle previous tag, maybe acting on its data
        Return that tag
        """
        if not self._stateStack:
            return

        # handle data from previous tag
        if self._stateStack and self._stateStack[-1] == '#CDATA':
            # close previous tag because all data tags have no element contents
            assert self._stateStack[-1] == '#CDATA', str(self._stateStack)
            self._stateStack.pop()
            last = self._stateStack.pop()
            methodName = 'data_%s' % (last.replace('.','_'),)
            dataHandler = getattr(self, methodName, self.unknownData)
            dataHandler(self._stateStack[:], last, self._data)
            # clear data
            self._data = ""
            return last

    def unknown_starttag(self, tag, attrs):
        """Fires when an explicit opener is encountered.
        """
        self.implicitClose()

        # add this tag to the stack
        self._stateStack.append(tag)
        print ('  ' * len(self._stateStack)) + tag

    def unknown_endtag(self, tag):
        """Fires when an explicit closer is encountered.
        Close all tags contained by this one, and this one
        """
        last = self.implicitClose()

        while last != tag:
            last = self._stateStack.pop()
        assert last == tag, "%s ended before it began!" % (tag,)

        print ('  ' * (len(self._stateStack)+1)) + '/' + tag

    def data_fid(self, stack, tag, data):
        print data

    def data_dtserver(self, stack, tag, data):
        print data


class Options(usage.Options):
    synopsis = "parse directory"
    # optParameters = [[long, short, default, help], ...]

    def parseArgs(self, directory):
        self['directory'] = directory

    def postOptions(self):
        p = OFXParser()
        d = self['directory']
        for ofx in ['%s/%s.ofx' % (d,x) for x in 'account', 'statement']:
            doc = open(ofx).read()
            p.feed(doc)


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
