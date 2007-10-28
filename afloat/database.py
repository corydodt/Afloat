"""
Interact with the local storm database
"""
from storm import locals

from afloat.util import RESOURCE

class BankTransaction(object):
    __storm_table__ = 'banktxn'
    id = locals.RawStr(primary=True)
    account = locals.Unicode()
    type = locals.Unicode()
    amount = locals.Int() # stored in cents
    userDate = locals.Date()
    ledgerDate = locals.Date()
    memo = locals.Unicode()
    checkNumber = locals.Int()
    # ledgerBalance ? store the ledger balance after this txn, to verify?

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

if __name__ == '__main__':
    createTables()
    store = initializeStore()
    print store
