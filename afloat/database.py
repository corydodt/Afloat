"""
Interact with the local storm database.  Retrieve OFX, google events, etc. into
storm tables
"""
import datetime

from twisted.python import log

from storm import locals

from afloat.util import RESOURCE

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
    id = locals.Int(primary=True)
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
    import os
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

def getGvents(store):
    pass # TODO


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
    A BalanceDay for each day in the last 7 including today.
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
        if currentDay < today - days(6):
            del bdays[currentDay]

        if currentTomorrow == today:
            break

        currentDay = currentTomorrow

    # TODO - compute future balances against gvents (must come after matchup
    # step)

    return zip(*sorted(bdays.items()))[1]


if __name__ == '__main__':
    createTables()
    store = initializeStore()
    print store
