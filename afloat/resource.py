"""
Web resources
"""
import datetime

from zope.interface import implements
from twisted.internet import defer
from twisted.python import log

from nevow import rend, static, url, inevow, vhost, athena, loaders, page

from afloat.util import RESOURCE, days
from afloat.gvent import parsetxn

MONDAY = 1
FRIDAY = 5

class DataXML(rend.Page):
    docFactory = loaders.xmlfile(RESOURCE('templates/data.xml'))

    def __init__(self, account, report, *a, **kw):
        self.account = account
        self.report = report
        super(DataXML, self).__init__(*a, **kw)

    def render_days(self, ctx, data):
        tag = ctx.tag
        content = []
        pgOdd = tag.patternGenerator('oddDay')
        pgEven = tag.patternGenerator('evenDay')
        pgToday = tag.patternGenerator('today')

        today = datetime.datetime.today().date()

        bdays = self.report.balanceDays(self.account.id)
        for n, day in enumerate(bdays):
            if day.date == today:
                pat = pgToday()
            else:
                pat = (pgOdd if n%2==1 else pgEven)()

            weekday = int(day.date.strftime('%w'))
            if weekday in [MONDAY, FRIDAY]:
                pat.fillSlots('showName', 1)
            elif day.date == today:
                pat.fillSlots('showName', 1)
            else:
                pat.fillSlots('showName', 0)

            if not day.date == today:
                pat.fillSlots('date', formatDateWeekday(day.date))
            pat.fillSlots('balance', day.balance/100.)
            content.append(pat)

        return tag[content]

    def renderHTTP(self, ctx):
        """
        Set text/xml on the resource
        """
        req = inevow.IRequest(ctx)
        req.setHeader('content-type', 'text/xml')
        return rend.Page.renderHTTP(self, ctx)


class RegisterPage(rend.Page):
    docFactory = loaders.xmlfile(RESOURCE('templates/register.xhtml'))

    def __init__(self, account, report):
        self.account = account
        self.report = report

    def render_all(self, ctx, data):
        tag = ctx.tag
        tag.fillSlots("type", self.account.type)

        pg = tag.patternGenerator("transaction")

        innards = []
        for txn in self.report.transactions(self.account.id, recent=30):
            row = pg()
            f = row.fillSlots
            f("date", formatDateWeekday(txn.ledgerDate))
            f("memo", txn.memo)
            f("amount", formatCurrency(txn.amount))
            f("balance", formatCurrency(txn.ledgerBalance))
            innards.append(row)

        tag.fillSlots("register", innards)
        return ctx.tag


class AfloatPage(athena.LivePage):
    docFactory = loaders.xmlfile(RESOURCE('templates/afloatpage.xhtml'))
    addSlash = 1
    def __init__(self, report, *args, **kw):
        self.report = report
        self.accounts = self.report.accounts()
        super(AfloatPage, self).__init__(*args, **kw)
    
    def render_all(self, ctx, data):
        tag = ctx.tag

        summary = Summary(self.report)
        summary.setFragmentParent(self)
        tag.fillSlots('summary', summary)

        graphs = Graphs(self.report)
        graphs.setFragmentParent(self)
        tag.fillSlots('graphs', graphs)

        scheduler = Scheduler(self.report)
        scheduler.setFragmentParent(self)
        tag.fillSlots('scheduler', scheduler)

        return ctx.tag

    def locateChild(self, ctx, segs):
        for a in self.accounts:
            if segs[-1] == '%s.xml' % (a.id,):
                return DataXML(a, self.report), []
            elif segs[-1] == a.id:
                return RegisterPage(a, self.report), []
        return athena.LivePage.locateChild(self, ctx, segs)


class Summary(athena.LiveElement):
    """
    Summary at the top showing balances, hover to show holds or big
    transactions
    """
    docFactory = loaders.xmlfile(RESOURCE("templates/Summary"))
    jsClass = u'Afloat.Summary'

    def __init__(self, report, *a, **kw):
        self.report = report
        self.accounts = self.report.accounts()
        super(Summary, self).__init__(*a, **kw)

    @page.renderer
    def summary(self, req, tag):
        pg = tag.patternGenerator('balance')
        content = []
        for account in self.accounts:
            pat = pg()
            pat.fillSlots('accountType', account.type)
            pat.fillSlots('ledger', '%.2f' % (account.ledgerBalance/100.,))
            pat.fillSlots('available', '%.2f' % (account.availableBalance/100.,))
            pat.fillSlots('account', account.id)
            if account.regulationDCount:
                remaining = account.regulationDMax - account.regulationDCount
                if remaining > 0:
                    regDPat = pat.patternGenerator("regulationD")()
                else:
                    regDPat = pat.patternGenerator("regulationDWarning")()
                regDPat.fillSlots('regDCount', remaining)
                regDPat.fillSlots('regDMax', account.regulationDMax)
                pat.fillSlots('regulationD', regDPat)
            else:
                pat.fillSlots('regulationD', [])
            content.append(pat)
        return tag[content]

    @page.renderer
    def hiddenSummary(self, req, tag):
        accounts = self.report.accounts()

        pgHold = tag.patternGenerator("holdTable")
        pgThreeDeposits = tag.patternGenerator("threeDepositsTable")
        pgThreeDebits = tag.patternGenerator("threeDebitsTable")
        for account in self.report.accounts():
            hdiv = pgHold()
            htab = hdiv.patternGenerator("t")()
            pg1 = htab.patternGenerator("holdItem")
            for hold in self.report.holds(account.id):
                row = pg1()
                row.fillSlots('amount', formatCurrency(hold.amount))
                row.fillSlots('description', hold.description)
                htab[row]
            hdiv[htab]
            hdiv.fillSlots('account', account.id)
            tag['\n', hdiv, '\n']

            depdiv = pgThreeDeposits()
            deptab = depdiv.patternGenerator("t")()
            pg2 = deptab.patternGenerator("threeDepositsItem")
            for dep in self.report.last3Deposits(account.id):
                row = pg2()
                row.fillSlots('date', formatDateWeekday(dep.ledgerDate))
                row.fillSlots('amount', formatCurrency(dep.amount))
                row.fillSlots('memo', dep.memo)
                deptab[row]
            depdiv[deptab]
            depdiv.fillSlots('account', account.id)
            tag['\n', depdiv, '\n']

            debdiv = pgThreeDebits()
            debtab = debdiv.patternGenerator("t")()
            pg3 = debtab.patternGenerator("threeDebitsItem")
            for deb in self.report.last3BigDebits(account.id):
                row = pg3()
                row.fillSlots('date', formatDateWeekday(deb.ledgerDate))
                row.fillSlots('amount', formatCurrency(deb.amount))
                row.fillSlots('memo', deb.memo)
                debtab[row]
            debdiv[debtab]
            debdiv.fillSlots('account', account.id)
            tag['\n', debdiv, '\n']

        return tag

    @page.renderer
    def debugUpdate(self, req, tag):
        if self.report.config['debug']:
            return tag
        return []

    @athena.expose
    def updateNow(self):
        """
        Immediately get the freshest ofx/gvents
        """
        assert self.report.config['debug']
        return self.report.update()


class Graphs(athena.LiveElement):
    """
    The graph showing balance and predicted balance
    """
    docFactory = loaders.xmlfile(RESOURCE("templates/Graphs"))
    jsClass = u'Afloat.Graphs'
    def __init__(self, report, *a, **kw):
        self.report = report
        self.accounts = report.accounts()
        super(Graphs, self).__init__(*a, **kw)

    def getInitialArguments(self):
        return [[(a.type, a.id) for a in self.accounts]]

    @page.renderer
    def selector(self, req, tag):
        pg = tag.patternGenerator("accountType")
        content = []
        for account in self.accounts:
            pat = pg()
            pat.fillSlots('accountType', account.type)
            content.append(pat)
        return tag[content]

    @page.renderer
    def allGraphs(self, req, tag):
        pg = tag.patternGenerator("oneGraph")
        content = []
        for account in self.accounts:
            pat = pg()
            pat.fillSlots('accountType', account.type)
            content.append(pat)
        return tag[content]


def differentWeek(d1, d2):
    """True if d1 and d2 are in different weeks of the year (i.e. at least one
    monday@midnight between them)
    """
    return d1.strftime('%U') != d2.strftime('%U')


class RescheduleReport(athena.LiveElement):
    """
    Display the transactions that will be rescheduled/killed
    """
    docFactory = loaders.xmlfile(RESOURCE("templates/RescheduleReport"))

    def __init__(self, report, toForget, toReschedule):
        self.report = report
        self.toForget = toForget
        self._forgotten = []
        self.toReschedule = toReschedule
        self._rescheduled = []

    @page.renderer
    def forgottenTransactions(self, req, tag):
        pg = tag.patternGenerator("forgottenRow")
        rows = []
        if self._forgotten:
            for txn in self._forgotten:
                pat = pg()
                pat.fillSlots('amount', formatCurrency(txn.amount))
                pat.fillSlots('title', txn.title)
                pat.fillSlots('originalDate', formatDateWeekday(txn.originalDate))
                rows.append(pat)
            tag.fillSlots('rows', rows)
            return tag
        return []

    @page.renderer
    def rescheduledTransactions(self, req, tag):
        pg = tag.patternGenerator("rescheduledRow")
        rows = []
        if self._rescheduled:
            for txn in self._rescheduled:
                pat = pg()
                pat.fillSlots('amount', formatCurrency(txn.amount))
                pat.fillSlots('title', txn.title)
                rows.append(pat)
            tag.fillSlots('rows', rows)
            return tag
        return []

    def forgetOneTransaction(self, href):
        today = datetime.datetime.today().date()
        d = self.report.removeItem(href)
        log.msg("** Started forgetOne (in resource.RescheduleReport)")

        def changed(txn):
            log.msg('** forgot %s' % (txn.title,))
            self._forgotten.append(txn)

        d.addCallback(changed)
        return d

    def rescheduleOneTransaction(self, href):
        today = datetime.datetime.today().date()
        d = self.report.rescheduleOne(href)
        log.msg("** Started rescheduleOne (in resource.RescheduleReport)")

        def changed(txn):
            log.msg('** rescheduled %s' % (txn.title,))
            self._rescheduled.append(txn)

        d.addCallback(changed)
        return d

    def rescheduleThings(self):
        """
        Do all the rescheduling and descheduling required to render this.
        This is an EVIL HACK.  I should just be able to do those things inline
        as I call the render methods, but when I do, CPU spikes up to 100%.
        This workaround instead front-loads the deferred, allowing me to
        return a RescheduleReport (from Scheduler.massUnschedule) that is able
        to be rendered synchronously.
        """
        dl = []
        for href in self.toReschedule:
            dl.append(self.rescheduleOneTransaction(href))
        for href in self.toForget:
            dl.append(self.forgetOneTransaction(href))
        return defer.DeferredList(dl, fireOnOneErrback=True)


class Scheduler(athena.LiveElement):
    """
    User interface for adding new future transactions
    """
    docFactory = loaders.xmlfile(RESOURCE("templates/Scheduler"))
    jsClass = u'Afloat.Scheduler'
    def __init__(self, report, *a, **kw):
        self.report = report
        super(Scheduler, self).__init__(*a, **kw)

    @page.renderer
    def lateTransactions(self, req, tag):
        pg = tag.patternGenerator("lateRow")
        lates = self.report.lateTransactions()
        for late in lates:
            tr = pg()
            tr.fillSlots('amount', formatCurrency(late.amount))
            tr.fillSlots('originalDate', formatDateWeekday(late.originalDate))
            tr.fillSlots('title', late.title)
            tr.fillSlots('href', late.href)
            tag[tr]
        return tag

    @page.renderer
    def scheduled(self, req, tag):
        pgDebit = tag.patternGenerator("debit")
        pgDeposit = tag.patternGenerator("deposit")
        pgBlank = tag.patternGenerator("blank")
        pg = tag.patternGenerator("contents")

        def putBlank(item):
            blank = pgBlank()
            ed = item.expectedDate
            monday = ed - days(ed.weekday())
            blank.fillSlots('week', monday.strftime('%m/%d'))
            tag[blank]

        coming = self.report.upcomingScheduled()
        last = None

        for item in coming:
            pat = pg()

            # put a blank row between weeks
            if last is None:
                putBlank(item)
            else:
                if differentWeek(last.expectedDate, item.expectedDate):
                    putBlank(item)

            pat.fillSlots('amount', formatCurrency(item.amount))
            pat.fillSlots('memo', item.title)
            pat.fillSlots('date', formatDateWeekday(item.expectedDate))
            pat.fillSlots('href', item.href)
            if item.paidDate:
                pgStatus = pat.patternGenerator('statusPaid')
            else:
                pgStatus = pat.patternGenerator('statusPending')
            pat.fillSlots('paidColumn', pgStatus())

            if item.amount >= 0:
                container = pgDeposit()
            else:
                container = pgDebit()

            container.fillSlots('contents', pat)

            tag[container]

            last = item
        return tag

    @athena.expose
    def unschedule(self, href):
        """
        Remove the specified item from the google calendar
        """
        d = self.report.removeItem(href)
        d.addCallback(lambda txn: u"OK")
        return d

    @athena.expose
    def massUnschedule(self, toForget, toReschedule):
        """
        @arg toForget: a list of the scheduled txns to forget
        @arg toReschedule: a list of the scheduled txns to reschedule
        """
        rr = RescheduleReport(self.report, toForget, toReschedule)
        rr.setFragmentParent(self)
        d_ = rr.rescheduleThings()
        d_.addCallback(lambda _done: rr)
        return d_

    @athena.expose
    def schedule(self, value):
        """
        Put a new item on the google calendar.  Then re-get all items from the
        calendar.
        """
        # this will raise a NoAmountError if there's no amount
        t = parsetxn.TxnTitle.fromString(value)
        d = self.report.quickAddItem(value)
        d.addCallback(lambda _: self.report.update())
        return d


def formatDateWeekday(dt):
    return dt.strftime('%a %m/%d')


def formatCurrency(amt):
    return '%.2f' % (amt/100.,)


class Root(rend.Page):
    """
    Adds child nodes for things common to anonymous and logged-in root
    resources.
    """
    addSlash = True  # yeah, we really do need this, otherwise 404 on /

    #def _child_sandbox(self, ctx):
    #    from goonmill._sparqlsandbox import *
    #    return SandboxPage()
    def child_static(self, ctx):
        return static.File(RESOURCE('static'))

    def child_app(self, ctx):
        return AfloatPage(self.service.report)

    def renderHTTP(self, ctx):
        return url.root.child("app")


class VhostFakeRoot:
    """
    I am a wrapper to be used at site root when you want to combine 
    vhost.VHostMonsterResource with nevow.guard. If you are using guard, you 
    will pass me a guard.SessionWrapper resource.
    """
    implements(inevow.IResource)
    def __init__(self, wrapped):
        self.wrapped = wrapped
    
    def renderHTTP(self, ctx):
        return self.wrapped.renderHTTP(ctx)
        
    def locateChild(self, ctx, segments):
        """Returns a VHostMonster if the first segment is "vhost". Otherwise
        delegates to the wrapped resource."""
        if segments[0] == "VHOST":
            return vhost.VHostMonsterResource(), segments[1:]
        else:
            return self.wrapped.locateChild(ctx, segments)


