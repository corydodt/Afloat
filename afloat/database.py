"""
Interact with the local storm database.  Retrieve OFX, google events, etc. into
storm tables
"""
import os
import datetime

from twisted.python import log
from twisted.internet import defer

from storm import locals

from afloat.util import RESOURCE, days
from afloat.gvent.readcal import parseKeywords
from afloat.gvent import protocol

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
    bankId = locals.Unicode()
    amount = locals.Int() # cents!
    checkNumber = locals.Int()
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

    @classmethod
    def log(cls, store, service, severity, description):
        now = datetime.datetime.today()
        nl = NetworkLog()
        nl.eventDateTime = now
        assert service in ('gvent', 'ofx')
        nl.service = service
        nl.description = description
        assert severity in ('ERROR', 'OK')
        nl.severity = severity

        store.add(nl)
        store.commit()


class BalanceDay(object):
    """
    The latest balance on a given day
    """
    def __init__(self, date, balance):
        self.date = date
        self.balance = balance


class AfloatReport(object):
    """
    The model for interacting with report data

    TODO - eliminate defaultAccount and add a better API that lets us inspect 
    gvents for each account.  (1 calendar per account?)
    """
    def __init__(self, store, config):
        self.store = store
        self.config = config

    def update(self):
        """
        Request data feeds from google and ofx, and mash them up
        """
        # set up requests for event and bank data retrieval
        from afloat.ofx import get

        c = self.config

        getter = get.Options()
        getter.update(self.config)

        # keep these processes from being garbage collected
        self._ofxDeferred = self.getOfx(
                getter.doGetting,
                encoding=c['encoding'])
        # store the results, successful or not, in the database

        def logSuccess(_, service):
            NetworkLog.log(self.store, service, u'OK', u'Success')

        def logFailure(f, service):
            log.msg("** Logging to the database: Service %s failed" %
                    (service,) )
            NetworkLog.log(self.store, service, u'ERROR',
                    unicode(f))
            log.err(f)

        self._ofxDeferred.addCallback(logSuccess, u'ofx')
        self._ofxDeferred.addErrback(logFailure, u'ofx')
        self._ofxDeferred.addErrback(log.err)

        # getGvents must be called after getOfx so new accounts can be
        # created.
        _gventDeferred = self._ofxDeferred.addCallback(
                lambda _: self.getGvents(account=c['defaultAccount'],))

        _gventDeferred.addCallback(logSuccess, u'gvent')
        _gventDeferred.addErrback(logFailure, u'gvent')
        _gventDeferred.addErrback(log.err)

        _gventDeferred.addCallback(lambda _: self.matchup())
        _gventDeferred.addErrback(log.err)

    def getOfx(self, request, **kw):
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
            p.debug = self.config['debug']

            p.feed(ofx)

            # create regular transactions
            for account in p.banking.accounts.values():
                self.updateAccount(account)
                for txn in account.transactions.values():
                    self.newTransaction(account.id, txn)

                # create holds
                for hold in account.holds:
                    self.newHold(account.id, hold)

                # scrub holds that have been applied by skipping all holds
                # that no longer in the ofx
                self.scrubHolds(account.id, account.holds)

            self.store.commit()
            return p.banking

        d.addCallback(gotOfx)
        return d

    def scrubHolds(self, accountId, ofxHolds):
        """
        Any holds in the database which do not correspond to holds in the bank
        are removed as no longer valid.
        """
        storeHolds = self.store.find(Hold, Hold.account == accountId)
        # use dicts like sets to determine which are missing, since holds have
        # no unique keys.
        left = dict([((h.amount, h.description), h) for h in storeHolds])
        right = dict([((h.amount, h.description), h) for h in ofxHolds])
        missing = [i[1] for i in left.items() if i[0] not in right.keys()]

        for h in missing:
            log.msg("** HOLD %s FOR $%.2f WENT AWAY" % (h.description,
                h.amount/100.))
            self.store.remove(h)

        self.store.commit()

    def newHold(self, accountId, hold):
        """
        Do CRUD operations on ofx holds we downloaded
        """
        # holds don't have ids, so just match on description/amount.
        matched = self.store.find(Hold, 
                Hold.description == hold.description,
                Hold.amount == hold.amount,
                Hold.account == accountId).one()
        if matched:
            if hold.dateApplied and not matched.dateApplied:
                matched.dateApplied = hold.dateApplied
        if not matched:
            new1 = Hold()
            new1.description = hold.description
            new1.amount = hold.amount
            new1.account = accountId
            new1.dateApplied = hold.dateApplied
            self.store.add(new1)
        self.store.commit()

    def newTransaction(self, accountId, txn):
        """
        Do CRUD operations on ofx txns we downloaded
        """
        bankTxn = self.store.get(BankTransaction, txn.id)
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
            self.store.add(bankTxn)

    def getGvents(self, **kw):
        """
        Retrieve gvents from afloat.gvent.protocol
        """
        account = kw['account']

        date1 = datetime.datetime.today() - days(1)
        date2 = date1 + days(self.config['lookAheadDays'] + 1)

        d = protocol.getGvents(date1, date2)

        def gotGvents(gvents):
            for event in gvents:
                self.newScheduledTransaction(account, event)
            gventSet = set([g.href for g in gvents])
            
            # Look for scheduledtxn items that have disappeared from the
            # google feed; these should be removed from scheduledtxn
            log.msg("CHECKING FOR REMOVED GVENTS")
            ST = ScheduledTransaction
            scheduled = self.store.find(ST, locals.And( ST.expectedDate >=
                date1, ST.expectedDate <= date2))
            schedSet = set([s.href for s in scheduled])

            removedSet = schedSet - gventSet
            for sched in scheduled:
                if sched.href in removedSet:
                    log.msg("*** TRANSACTION DISAPPEARED: %s %s" %
                            (sched.expectedDate, sched.title))
                    self.store.remove(sched)

            self.store.commit()

        d.addCallback(gotGvents)
        return d

    def newScheduledTransaction(self, accountId, event):
        """
        Do CRUD operations on gvents we downloaded
        """
        schedTxn = self.store.get(ScheduledTransaction, event.href)

        e = event

        new = 0

        if schedTxn is None:
            schedTxn = ScheduledTransaction()
            schedTxn.href = e.href
            new = 1

        if e.fromAccount is None and e.toAccount is None:
            schedTxn.fromAccount = unicode(accountId)
        else:
            # set accounts, looking up the actual ids from the account type
            fa = e.fromAccount
            if fa:
                id = self.store.find(Account, Account.type==fa).one().id
            else:
                id = unicode(self.config['defaultAccount'])
            schedTxn.fromAccount = id
            ta = e.toAccount
            if ta:
                assert e.fromAccount, "toAccount set without fromAccount"
                ta = self.store.find(Account, Account.type==ta).one().id
                schedTxn.toAccount = ta

        assert schedTxn.fromAccount is not None
        schedTxn.amount = int(e.amount)
        schedTxn.title = e.title
        schedTxn.checkNumber = e.checkNumber
        schedTxn.expectedDate = e.expectedDate
        schedTxn.originalDate = e.originalDate
        schedTxn.paidDate = e.paidDate

        if new:
            self.store.add(schedTxn)
        self.store.commit()

    def updateAccount(self, account):
        """
        Make changes to an account in account table when it already exists
        """
        bankAcct = self.store.get(Account, account.id)
        if bankAcct is None:
            bankAcct = Account()
            bankAcct.id = account.id
            self.store.add(bankAcct)
        bankAcct.type = account.type
        bankAcct.ledgerBalance = account.ledgerBal
        bankAcct.ledgerAsOfDate = account.ledgerDate
        bankAcct.availableBalance = account.availBal
        bankAcct.availableAsOfDate = account.availDate
        # bankAcct.regulationDCount =
        # bankAcct.regulationDMax =
        self.store.commit()

    def balanceDays(self, account):
        """
        A BalanceDay for each day in the last 'lookBehindDays' including
        today, and in the next 'lookAheadDays'.
        Compute by looking at the last transaction-with-balance on each day;
        fill in days with no transactions by carrying over from previous day.
        """
        # do bank transactions first.
        today = datetime.date.today()
        beginDate = today - days(self.config['lookBehindDays'] + 7)
        txns = self.store.find(BankTransaction,
                locals.And(
                    BankTransaction.ledgerDate >= beginDate,
                    BankTransaction.account == account,
                    )).order_by(BankTransaction.ledgerDate, BankTransaction.id)
        txns = list(txns)

        # create balance days for each bank txn
        bdays = {}
        for t in txns:
            bdays[t.ledgerDate] = BalanceDay(t.ledgerDate, t.ledgerBalance)

        # inspect each day slot to make sure there's a balance in it. if no
        # balance, carry over the previous day's balance
        currentDay = beginDate
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
            # to see last lookBehindDays
            if currentDay < today - days(self.config['lookBehindDays'] - 1):
                del bdays[currentDay]

            if currentTomorrow == today:
                break

            currentDay = currentTomorrow


        # Get the scheduled gvent transactions now and apply them.
        # For balance purposes, skip any transactions that were PAID.

        froms = [t for t in self.upcomingScheduled()
                if t.paidDate is None]

        lastDay = today

        for n in range(self.config['lookAheadDays']):
            currentDay = today + days(n)
            currentBalance = bdays[lastDay].balance
            for txn in froms:
                if txn.expectedDate == currentDay:
                    currentBalance = currentBalance + txn.amount

            bdays[currentDay] = BalanceDay(currentDay, currentBalance)
            lastDay = currentDay

        return zip(*sorted(bdays.items()))[1]

    def upcomingScheduled(self, ):
        """
        Return all scheduled transactions for the next
        self.config['lookAheadDays'] days, for the given account
        """
        today = datetime.date.today()
        periodEnd = today + days(self.config['lookAheadDays'])

        ST = ScheduledTransaction
        found = self.store.find(ST,
                locals.And(
                    ST.expectedDate <= periodEnd,
                    ST.fromAccount == unicode(self.config['defaultAccount']),
                    )).order_by(ST.expectedDate)
        return  list(found)

    def matchup(self):
        """
        Flag as paid any scheduled transactions that were found in the register
        recently, by matching scheduled titles with bank memos, dates and amounts
        within $0.05

        Next, bubble forward any unmatched transactions; for LATE
        transactions, remember to ask the user next time for a confirmation or
        delete.

        Finally fix these items in the google database, setting extended properties
        and titles appropriately.
        """
        dl = []

        pendings = self.store.find(ScheduledTransaction, 
                ScheduledTransaction.paidDate == None)
        for pending in pendings:
            matched = self.tryMatch(pending)
            if matched:
                pending.paidDate = matched.ledgerDate
                # overwrite the scheduled amount with the actual amount, when
                # they differ (within the $0.05 tolerance)
                pending.amount = matched.amount
                pending.title = pending.title + '[PAID]'

                print 'Found a matchup on "%s" == "%s"' % (
                        pending.title, matched.memo)
                d_ = protocol.putMatchedTransaction(pending.href,
                        pending.paidDate, pending.amount, pending.title)
                dl.append(d_)
            else:
                continue
        self.store.commit()

        ## TODO.. bubble txns forward and flag LATE txns

        return defer.DeferredList(dl)

    def tryMatch(self, schedtxn):
        """
        For one scheduled transaction, try to match it with any bank transaction
        """
        mydate = schedtxn.expectedDate
        myamount = schedtxn.amount

        todayTxns = self.store.find(BankTransaction, 
                BankTransaction.ledgerDate == mydate)

        # look at check numbers first to shortcut
        if schedtxn.checkNumber:
            for txn in todayTxns:
                if txn.checkNumber == schedtxn.checkNumber:
                    return txn
            return None

        for txn in todayTxns:
            ST = ScheduledTransaction

            # skip any transaction that already has a corresponding paid
            # scheduledTxn
            if self.store.find(ST, ST.bankId == txn.id).count() > 0:
                continue

            # skip any that don't match within $0.05
            if abs(txn.amount - schedtxn.amount) > 5:
                continue

            # split into words and remove money amounts, then look at the memo. we
            # should match all words.
            txnWords = txn.memo.split()
            matchCount = 0
            myWords = parseKeywords(txn.memo)
            for kw in myWords:
                if kw in txnWords:
                    matchCount += 1
            # all words found? this is the txn.
            if matchCount == len(myWords):
                return txn

            # TODO (maybe) - more probability-based, search-like matching

    def accounts(self):
        """
        Return all accounts as a list
        """
        qry = self.store.find(Account).order_by(Account.type)
        return [a for a in qry]

    def holds(self, account):
        rs = self.store.find(Hold,
                Hold.account==account).order_by(Hold.amount)
        return rs

    def last3Deposits(self, account):
        rs = self.store.find(BankTransaction,
                locals.And(
                    BankTransaction.account==account,
                    BankTransaction.amount > 0,
                    ),
                )
        ret = rs.order_by(locals.Desc(BankTransaction.ledgerDate),
                    locals.Desc(BankTransaction.id))[:3]
        return ret

    def last3BigDebits(self, account):
        """
        Somewhat arbitrarily returns the last 3 debits of amounts greater than
        config['bigAmount']
        """
        bigAmount = self.config['bigAmount']
        rs = self.store.find(BankTransaction,
                locals.And(
                    BankTransaction.account==account,
                    BankTransaction.amount < bigAmount,
                    ))
        ret = rs.order_by(locals.Desc(BankTransaction.ledgerDate),
                    locals.Desc(BankTransaction.id))[:3]
        return ret

    def transactions(self, account):
        """
        All the transactions
        """
        return self.store.find(BankTransaction, BankTransaction.account ==
                account).order_by(BankTransaction.ledgerDate,
                        BankTransaction.id)

def createTables():
    """
    Run sqlite to create the database tables the app needs
    """
    os.system('sqlite3 -echo %s < %s' % (RESOURCE('afloat.db'), RESOURCE('tables.sql'),))

def initializeStore():
    """
    Gimme a storm database.
    """
    db = locals.create_database('sqlite:///%s' % (RESOURCE('afloat.db'),))
    store = locals.Store(db)
    return store


if __name__ == '__main__':
    createTables()
    store = initializeStore()
    print store
