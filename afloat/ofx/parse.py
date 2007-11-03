# vi:ft=python
import sys
import datetime

from twisted.python import usage

import sgmllib

from afloat.util import RESOURCE


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

    def textReport(self):
        s = []
        w = s.append
        w("ACCOUNTS!")
        for id, account in sorted(self.accounts.items()):
            w(' #' + id)
            w('  HOLDS!')
            for hold in account.holds:
                w('   %s %s' % (hold.amount, hold.description))
            w('  TXNS!')
            for id, txn in sorted(account.transactions.items()):
                w('   %s %s %s' % (txn.amount, txn.date, txn.memo))

        return '\n'.join(s)


class Account(object):
    """
    A single account, with all your transactions
    """
    def __init__(self):
        self.transactions = {}
        self.holds = []

    def addTransaction(self, txn):
        self.transactions[txn.id] = txn

    def addHold(self, hold):
        self.holds.append(hold)


class Transaction(object):
    """
    One transaction (date, memo, checknum, amount)
    """
    def __init__(self):
        self.checkNumber = None


class Hold(object):
    pass


class OFXParser(sgmllib.SGMLParser):
    """
    Get financials out.  We need (from signon, acctlist, bankstmt):
.      /ofx/signonmsgsrsv1/dtserver
.                         /fi/fid (to verify)
.                         /users.primacn (to verify)
X          /signupmsgsrsv1/acctinfors/acctinfo/bankacctinfo/bankacctfrom/acctid (all available, key)
X                                                                       /accttype (all by acctid)
X                                                          /users.bankinfo/ledgerbal/balamt (all by acctid)
X                                                                                   /dtasof (all by acctid)
X                                                                         /availbal/balamt (all by acctid)
X                                                                                  /dtasof (all by acctid)
X                                                                         /hold/dtapplied (all by acctid, key)
X                                                                              /desc  (all by acctid by dtapplied)
X                                                                              /amt  (all by acctid by dtapplied)
.                                                                         /regdcnt (all by accountid)
.                                                                         /regdmax (all by accountid)
X          /bankmsgsrsv1/stmtrnsrs/stmtrs/bankacctfrom/acctid
X                                        /banktranlist/stmttrn/fitid (all available, key)
X                                                             /trntype
X                                                             /trnamt
X                                                             /dtposted
_                                                             /dtuser
X                                                             /memo
X                                                             /checknum
X                                                             /users.stmt/trnbal (to verify)
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
        self._data = u""
        self._stateStack = []
        self.banking = Banking()
        self.currentAccount = None
        self.currentTransaction = None
        self.debug = False
        self.encoding = None

    def handle_data(self, data):
        """
        This is called when some new data arrives.
        We don't do anything with the data yet, because there might be more
        before the end of the tag.
        """
        if data.strip() and self._stateStack:
            self._data = self._data + data.decode(self.encoding)
            if self._stateStack[-1] != '#CDATA':
                self._stateStack.append('#CDATA')

    def unknownData(self, stack, tag, data):
        self.printDebug('  ' * len(self._stateStack) + '    #CDATA')

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
            dataHandler(self._stateStack[:], last, self._data.strip())
            # clear data
            self._data = u""
            return last

    def finish_starttag(self, tag, attrs):
        """Fires when an explicit opener is encountered.
        """
        self.implicitClose()

        # add this tag to the stack
        self._stateStack.append(tag)
        self.printDebug(('  ' * len(self._stateStack)) + tag)
        return sgmllib.SGMLParser.finish_starttag(self, tag, attrs)

    def unknown_endtag(self, tag):
        """Fires when an explicit closer is encountered.
        Close all tags contained by this one, and this one
        """
        last = self.implicitClose()

        while last != tag:
            last = self._stateStack.pop()
        assert last == tag, "%s ended before it began!" % (tag,)

        self.printDebug(('  ' * (len(self._stateStack)+1)) + '/' + tag)

    def data_fid(self, stack, tag, data):
        # TODO - verify this is my bank (config file?)
        self.printDebug(data)

    def data_users_primacn(self, stack, tag, data):
        # TODO - verify this is my primary account (config file?)
        self.printDebug(data)

    def data_dtserver(self, stack, tag, data):
        # TODO - record this in the network log
        self.printDebug(data)

    def data_acctid(self, stack, tag, data):
        if stackEndsWith(stack, 'acctinfo/bankacctinfo/bankacctfrom'):
            self.currentAccount.id = data
            self.printDebug('** NEW ACCOUNT: %s' % (data,))
            self.banking.addAccount(self.currentAccount)
        elif stackEndsWith(stack, 'stmtrs/bankacctfrom'):
            self.currentAccount = self.banking.getAccount(data)

    def data_balamt(self, stack, tag, data):
        if stackEndsWith(stack, 'users.bankinfo/ledgerbal'):
            self.currentAccount.ledgerBal = parseCurrency(data)
        elif stackEndsWith(stack, 'users.bankinfo/availbal'): 
            self.currentAccount.availBal = parseCurrency(data)
        elif stackEndsWith(stack, 'stmtrs/ledgerbal'): 
            self.printDebug(data) # TODO - verify against acctinfo ledgerbal
        elif stackEndsWith(stack, 'stmtrs/availbal'): 
            self.printDebug(data) # TODO - verify against acctinfo availbal

    def start_bankacctinfo(self, attrs):
        self.currentAccount = Account()

    def start_hold(self, attrs):
        hold = self.currentTransaction = Hold()
        self.printDebug("** NEW HOLD")
        self.currentAccount.addHold(hold)

    def data_amt(self, stack, tag, data):
        if stackEndsWith(stack, 'hold'):
            hold = self.currentTransaction
            hold.amount = parseCurrency(data)

    def data_desc(self, stack, tag, data):
        if stackEndsWith(stack, 'hold'):
            hold = self.currentTransaction
            hold.description = data

    def data_dtapplied(self, stack, tag, data):
        if stackEndsWith(stack, 'hold'):
            hold = self.currentTransaction
            # dtapplied has its own stupid date format
            hold.dateApplied = parseDate2(data)

    def data_regdmax(self, stack, tag, data):
        # TODO - show this in the UI somewhere
        self.printDebug(data)

    def data_regdcnt(self, stack, tag, data):
        # TODO - show this in the UI somewhere
        self.printDebug(data)

    def data_trntype(self, stack, tag, data):
        txn = self.currentTransaction
        txn.type = data

    def data_trnamt(self, stack, tag, data):
        txn = self.currentTransaction
        txn.amount = parseCurrency(data)

    def data_fitid(self, stack, tag, data):
        txn = self.currentTransaction
        txn.id = data
        self.printDebug("** NEW TXN: %s" % (data,))
        self.currentAccount.addTransaction(txn)

    def data_dtposted(self, stack, tag, data):
        if stackEndsWith(stack, 'stmttrn'):
            self.currentTransaction.date = parseDate(data)

    def data_memo(self, stack, tag, data):
        if stackEndsWith(stack, 'stmttrn'):
            self.currentTransaction.memo = data

    def data_dtasof(self, stack, tag, data):
        if stackEndsWith(stack, 'users.bankinfo/ledgerbal'):
            self.currentAccount.ledgerDate = parseDate(data)
        elif stackEndsWith(stack, 'users.bankinfo/availbal'):
            self.currentAccount.availDate = parseDate(data)
        elif stackEndsWith(stack, 'stmtrs/ledgerbal'):
            self.printDebug(data)
        elif stackEndsWith(stack, 'stmtrs/availbal'):
            self.printDebug(data)

    def start_stmttrn(self, attrs):
        self.currentTransaction = Transaction()

    def data_accttype(self, stack, tag, data):
        if stackEndsWith(stack, 'acctinfo/bankacctinfo/bankacctfrom'):
            self.currentAccount.type = data

    def data_checknum(self, stack, tag, data):
        if stackEndsWith(stack, 'stmttrn'):
            self.currentTransaction.checkNumber = int(data)

    def data_trnbal(self, stack, tag, data):
        if stackEndsWith(stack, 'users.stmt'):
            self.currentTransaction.ledgerBalance = parseCurrency(data)

    def printDebug(self, s):
        if self.debug:
            print s


def parseCurrency(s):
    """Return cents
    """
    return int(float(s) * 100)


def parseDate2(s):
    """Return a datetime object"""
    if s == 'None':
        return None
    return datetime.datetime.strptime(s[:10], '%m/%d/%Y')


def parseDate(s):
    """Return a datetime object"""
    if s == 'None':
        return None
    return datetime.datetime.strptime(s[:14], '%Y%m%d%H%M%S')


def stackEndsWith(stack, s):
    """
    True if the last elements match s.split('/')
    """
    end = s.split('/')
    return stack[-len(end):] == end


class Options(usage.Options):
    synopsis = "parse"
    # optParameters = [[long, short, default, help], ...]
    optFlags = [['debug', 'd', 'Whether to print out debugging output'],
            ]

    def postOptions(self):
        execfile(RESOURCE('../config.py'), self)
        p = OFXParser()
        p.debug = self['debug']
        ofx = self.get('stream')
        if ofx is None:
            ofx = sys.stdin.read()
        p.encoding = self['encoding']
        p.feed(ofx)

        if self['debug']:
            print p.banking.textReport()


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
