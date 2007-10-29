"""
Interact with the local storm database.  Retrieve OFX, google events, etc. into
storm tables
"""
import glob
import tempfile
import shutil

from twisted.internet import defer
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
    # ledgerBalance ? store the ledger balance after this txn, to verify?


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
    os.system('sqlite3 -echo afloat.db < %s' % (RESOURCE('tables.sql'),))

def initializeStore():
    db = locals.create_database('sqlite:///%s' % (RESOURCE('afloat.db'),))
    store = locals.Store(db)
    return store

def getOfx(store, *requests, **kw):
    """
    Retrieve, then parse, the OFX into the storm database

    requests is a list of callables.  When called with a directory name, they
    should return a deferred which fires when the request is finished.

    The callable should write a file named *.ofx to the directory it was
    passed.

    kwargs:
        ofxEncoding: the encoding used in the ofx files to be retrieved (may
                     be set in config.py originally)
    """
    ofxEncoding = kw['ofxEncoding']

    def withTempdir(outdir):
        d = defer.Deferred()
        for request in requests:
            cb = lambda _, req=request: req(outdir)
            d.addCallback(cb)

        def gotOfxFiles(_):
            from afloat.ofx.parse import OFXParser
            p = OFXParser()
            p.ofxEncoding = ofxEncoding
            # TODO - get passed-in self['debug'] ?
            ## p.debug = self['debug']

            for ofx in glob.glob(outdir + '/account*.ofx'):
                doc = open(ofx).read()
                p.feed(doc)
            for ofx in glob.glob(outdir + '/statement*.ofx'):
                doc = open(ofx).read()
                p.feed(doc)

            for account in p.banking.accounts.values():
                updateAccount(store, account)
                for txn in account.transactions.values():
                    newTransaction(store, account.id, txn)
            store.commit()
            # TODO - matchups
            # TODO - create storm objects for Holds
            return p.banking

        d.addCallback(gotOfxFiles).addErrback(log.err)
        d.callback(None)
        return d

    tempdir = tempfile.mkdtemp()
    def doneWithTempdir(banking, tempdir):
        shutil.rmtree(tempdir)
        return banking
    return withTempdir(tempdir).addBoth(doneWithTempdir, tempdir)


def newTransaction(store, accountId, txn):
    if not store.get(BankTransaction, txn.id):
        bankTxn = BankTransaction()
        bankTxn.id = txn.id
        bankTxn.account = accountId
        bankTxn.type = txn.type
        bankTxn.amount = txn.amount
        # TODO userDate = 
        bankTxn.ledgerDate = txn.date
        bankTxn.memo = txn.memo
        # TODO checkNumber = 
        # TODO ledgerBalance? = 
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

if __name__ == '__main__':
    createTables()
    store = initializeStore()
    print store
