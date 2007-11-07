"""
Interact with the local storm database.  Retrieve OFX, google events, etc. into
storm tables
"""
import os
import datetime

from twisted.python import log
from twisted.internet import defer, reactor
from twisted.internet.protocol import ProcessProtocol

from storm import locals

from afloat.util import RESOURCE
from afloat.gvent.readcal import CalendarEventString

class BankTransaction(object):
    __storm_table__ = 'banktxn'
    id = locals.Unicode(primary=True)
    account = locals.Unicode()
    type = locals.Unicode()
    amount = locals.Int() # stored in cents
    userDate = locals.Date()
    ledgerDate = locals.Date()
    memo = locals.Unicode()
    checkNumber = locals.Int()
    ledgerBalance = locals.Int()


class Account(object):
    __storm_table__ = 'account'
    id = locals.Unicode(primary=True)
    type = locals.Unicode()
    ledgerBalance = locals.Int()
    ledgerAsOfDate = locals.Date()
    availableBalance = locals.Int()
    availableAsOfDate = locals.Date()
    regulationDCount = locals.Int()
    regulationDMax = locals.Int()


class Hold(object):
    __storm_table__ = 'hold'
    id = locals.Int(primary=True)
    account = locals.Unicode()
    amount = locals.Int() # cents!
    description = locals.Unicode()
    dateApplied = locals.Date()


class ScheduledTransaction(object):
    __storm_table__ = 'scheduledtxn'
    href = locals.Unicode(primary=True)
    bankId = locals.Int()
    amount = locals.Int() # cents!
    title = locals.Unicode()
    expectedDate = locals.Date()
    originalDate = locals.Date()
    fromAccount = locals.Unicode()
    toAccount = locals.Unicode()
    paidDate = locals.Date()


class NetworkLog(object):
    __storm_table__ = 'networklog'
    id = locals.Int(primary=True)
    eventDateTime = locals.DateTime()
    service = locals.Unicode() # gvent or ofx
    description = locals.Unicode()
    severity = locals.Unicode() # OK or ERROR


def createTables():
    os.system('sqlite3 -echo %s < %s' % (RESOURCE('afloat.db'), RESOURCE('tables.sql'),))

def initializeStore():
    db = locals.create_database('sqlite:///%s' % (RESOURCE('afloat.db'),))
    store = locals.Store(db)
    return store

def getOfx(store, request, **kw):
    """
    Retrieve, then parse, the OFX into the storm database

    request is a callable.  When called, they should return a deferred which
    fires with the ofx stream when the request is finished.

    kwargs:
        encoding: the encoding used in the ofx files to be retrieved (may
                  be set in config.py originally)
    """
    encoding = kw['encoding']

    d = request()

    def gotOfx(ofx):
        from afloat.ofx.parse import OFXParser
        p = OFXParser()
        p.encoding = encoding
        # TODO - get passed-in self['debug'] ?
        ## p.debug = self['debug']

        p.feed(ofx)
        open('/tmp/ofx.ofx', 'wb').write(ofx)

        for account in p.banking.accounts.values():
            updateAccount(store, account)
            for txn in account.transactions.values():
                newTransaction(store, account.id, txn)
        store.commit()
        # TODO - matchups
        # TODO - create storm objects for Holds
        return p.banking

    d.addCallback(gotOfx).addErrback(log.err)
    return d

def newTransaction(store, accountId, txn):
    """
    Do CRUD operations on ofx txns we downloaded
    """
    bankTxn = store.get(BankTransaction, txn.id)
    if bankTxn:
        # ledger balance can change in response to retroactive transactions
        # (i.e. the bank inserting an adjustment) - so always keep it up to
        # date
        if bankTxn.ledgerDate != txn.date:
            bankTxn.ledgerDate = txn.date
        if bankTxn.ledgerBalance != txn.ledgerBalance:
            bankTxn.ledgerBalance = txn.ledgerBalance

    else:
        bankTxn = BankTransaction()
        bankTxn.id = txn.id
        bankTxn.account = accountId
        bankTxn.type = txn.type
        bankTxn.amount = txn.amount
        # TODO userDate = 
        bankTxn.ledgerDate = txn.date
        bankTxn.memo = txn.memo
        bankTxn.checkNumber = txn.checkNumber
        bankTxn.ledgerBalance = txn.ledgerBalance
        store.add(bankTxn)

def updateAccount(store, account):
    bankAcct = store.get(Account, account.id)
    if bankAcct is None:
        bankAcct = Account()
        bankAcct.id = account.id
        store.add(bankAcct)
    bankAcct.type = account.type
    bankAcct.ledgerBalance = account.ledgerBal
    bankAcct.ledgerAsOfDate = account.ledgerDate
    bankAcct.availableBalance = account.availBal
    bankAcct.availableAsOfDate = account.availDate
    # bankAcct.regulationDCount =
    # bankAcct.regulationDMax =


class GVentProtocol(ProcessProtocol):
    """
    Communicate with "python -m afloat.gvent.readcal ..." to retrieve the calendar
    items on stdout
    """
    TERM = '\r\n'
    def __init__(self, *a, **kw):
        self.stream = ''
        self.gvents = []
        self.disconnectDeferreds = []

    def streamEndsWith(self, s):
        chars = len(s)
        self.stream.seek(-chars, 2)
        tail = self.stream.read()
        return tail == s

    def loadEventFromStream(self):
        """
        Load the last entire event from the stream
        """
        termPos = self.stream.find(self.TERM)
        while termPos >= 0:
            item = self.stream[:termPos]
            event = CalendarEventString.fromString(item)
            self.gvents.append(event)
            self.stream = self.stream[termPos + len(self.TERM):]
            termPos = self.stream.find(self.TERM)

    def outReceived(self, data):
        self.stream = self.stream + data
        if self.TERM in self.stream:
            self.loadEventFromStream()
            g = self.gvents[-1]

    def errReceived(self, data):
        print '***', data

    def processEnded(self, reason):
        """Notify our disconnects"""
        assert self.stream == '', self.stream
        for d in self.disconnectDeferreds:
            d.callback(reason)

    def notifyOnDisconnect(self):
        d = defer.Deferred()
        self.disconnectDeferreds.append(d)
        return d


def getGvents(store, **kw):
    """
    Run module afloat.gvent as a python process
    """
    password = kw['password']
    email = kw['email']
    calendar = kw['calendar']
    account = kw['account']

    pp = GVentProtocol()

    # TODO - d will be called back when process is running, use it if
    # necessary

    date1 = datetime.datetime.today() - days(1)
    date2 = date1 + days(17)

    date1 = date1.strftime('%Y-%m-%d')
    date2 = date2.strftime('%Y-%m-%d')

    args = ['python', '-m', 'afloat.gvent.readcal', 
         '--connect=%s//%s//%s' % (calendar, email, password),
         'get-events', '--fixup', date1, date2,
        ]
    cleanArgs = ['python', '-m', 'afloat.gvent.readcal', 
         '--connect=%s//%s//%s' % (calendar, email, '~~~~~~~~'),
         'get-events', '--fixup', date1, date2,
        ]
    print ' '.join(cleanArgs)
    pTransport = reactor.spawnProcess(pp, '/usr/bin/python', args,
            env=os.environ, usePTY=1)

    d = pp.notifyOnDisconnect()

    def gotGvents(_, proto):
        for event in proto.gvents:
            newScheduledTransaction(store, account, event)
        store.commit()

    d.addBoth(gotGvents, pp).addErrback(log.err)
    return d

def newScheduledTransaction(store, accountId, event):
    """
    Do CRUD operations on gvents we downloaded
    """
    schedTxn = store.get(ScheduledTransaction, event.href)
    if schedTxn is not None:
        pass
        # TODO - update it in the database

    else:
        e = event
        schedTxn = ScheduledTransaction()
        schedTxn.href = e.href
        if e.fromAccount is None and e.toAccount is None:
            schedTxn.fromAccount = unicode(accountId)
        else:
            # set accounts, looking up the actual ids from the account type
            fa = e.fromAccount
            if fa:
                fa = store.find(Account, Account.type==fa)[0].id
                schedTxn.fromAccount = fa
            ta = e.toAccount
            if ta:
                ta = store.find(Account, Account.type==ta)[0].id
                schedTxn.toAccount = ta

        schedTxn.amount = int(e.amount)
        schedTxn.title = e.title
        schedTxn.expectedDate = e.expectedDate
        schedTxn.originalDate = e.originalDate
        schedTxn.paidDate = e.paidDate
        store.add(schedTxn)


class BalanceDay(object):
    """
    The latest balance on a given day
    """
    def __init__(self, date, balance):
        self.date = date
        self.balance = balance


def days(amount):
    return datetime.timedelta(days=amount)


def balanceDays(store, account):
    """
    A BalanceDay for each day in the last 5 including today, and the next 16.
    Compute by looking at the last transaction-with-balance on each day;
    fill in days with no transactions by carrying over from previous day.
    """
    today = datetime.date.today()
    weeksAgo2 = today - days(14)
    txns = store.find(BankTransaction,
            locals.And(
                BankTransaction.ledgerDate >= weeksAgo2,
                BankTransaction.account == account,
                )).order_by(BankTransaction.ledgerDate)
    txns = list(txns)

    bdays = {}
    for t in txns:
        bdays[t.ledgerDate] = BalanceDay(t.ledgerDate, t.ledgerBalance)

    # inspect each day slot to make sure there's a balance in it. if no
    # balance, carry over the previous day's balance
    currentDay = weeksAgo2
    while currentDay <= today:
        currentTomorrow = currentDay + days(1)

        # skip up to the first date with a balance
        if not bdays.has_key(currentDay):
            currentDay = currentTomorrow
            continue

        if currentTomorrow not in bdays:
            bd = bdays[currentDay]
            bdays[currentTomorrow] = BalanceDay(currentTomorrow, bd.balance)

        # now clear the txn if it is not within 6 days, because we only want
        # to see last 7
        if currentDay < today - days(4):
            del bdays[currentDay]

        if currentTomorrow == today:
            break

        currentDay = currentTomorrow

    # TODO - matchups

    froms = scheduledNext3Weeks(store, account)

    tos = []
    for txn in froms:
        if txn.toAccount is not None:
            tos.append(txn.href)

    hasToAccount = lambda t: t.href in tos

    lastDay = today

    for n in range(16):
        currentDay = today + days(n)
        currentBalance = bdays[lastDay].balance
        for txn in froms:
            # if there is a TO ACCOUNT, then the FROM account is a debit
            adjustedAmount = (txn.amount if not hasToAccount(txn) else -txn.amount)
            if txn.expectedDate == currentDay:
                currentBalance = currentBalance + adjustedAmount

        bdays[currentDay] = BalanceDay(currentDay, currentBalance)
        lastDay = currentDay

    return zip(*sorted(bdays.items()))[1]


def scheduledNext3Weeks(store, account):
    """
    Return all scheduled transactions for the next 3 weeks, for the given
    account
    """
    today = datetime.date.today()
    next3Weeks = today + days(21)

    ST = ScheduledTransaction
    found = store.find(ST,
            locals.And(
                ST.expectedDate <= next3Weeks,
                ST.fromAccount == unicode(account),
                )).order_by(ST.expectedDate)
    return  list(found)



if __name__ == '__main__':
    createTables()
    store = initializeStore()
    print store
