"""
Web resources
"""

from zope.interface import implements

from nevow import rend, static, url, inevow, vhost, athena, loaders, page

from afloat.util import RESOURCE
from afloat import database

MONDAY = 1
FRIDAY = 5

class DataXML(rend.Page):
    docFactory = loaders.xmlfile(RESOURCE('templates/data.xml'))

    def __init__(self, account, service, *a, **kw):
        self.account = account
        self.service = service
        super(DataXML, self).__init__(*a, **kw)

    def render_days(self, ctx, data):
        tag = ctx.tag
        content = []
        pgOdd = tag.patternGenerator('oddDay')
        pgEven = tag.patternGenerator('evenDay')

        days = database.balanceDays(self.service.store, self.account.id)
        for n, day in enumerate(days):
            pat = (pgOdd if n%2==1 else pgEven)()
            weekday = int(day.date.strftime('%w'))
            if weekday in [MONDAY, FRIDAY]:
                pat.fillSlots('showName', 1)
            else:
                pat.fillSlots('showName', 0)
            pat.fillSlots('date', day.date.strftime('%a %m/%d'))
            pat.fillSlots('balance', day.balance/100.)
            content.append(pat)

        return tag[content]

    def renderHTTP(self, ctx):
        """
        Set text/xml on the resource
        """
        inevow.IRequest(ctx).setHeader('content-type', 'text/xml')
        return rend.Page.renderHTTP(self, ctx)


class AfloatPage(athena.LivePage):
    docFactory = loaders.xmlfile(RESOURCE('templates/afloatpage.xhtml'))
    addSlash = 1
    def __init__(self, service, *args, **kw):
        self.service = service 
        qry = service.store.find(database.Account).order_by(database.Account.type)
        self.accounts = [a for a in qry]
        super(AfloatPage, self).__init__(*args, **kw)
    
    def render_all(self, ctx, data):
        tag = ctx.tag

        summary = Summary(self.service)
        summary.setFragmentParent(self)
        tag.fillSlots('summary', summary)

        graphs = Graphs(self.service, self.accounts)
        graphs.setFragmentParent(self)
        tag.fillSlots('graphs', graphs)

        scheduler = Scheduler(self.service)
        scheduler.setFragmentParent(self)
        tag.fillSlots('scheduler', scheduler)

        return ctx.tag

    def locateChild(self, ctx, segs):
        for a in self.accounts:
            if segs[-1] == '%s.xml' % (a.id,):
                return DataXML(a, self.service), []
        return athena.LivePage.locateChild(self, ctx, segs)


class Summary(athena.LiveElement):
    """
    Summary at the top showing balances, hover to show holds or big
    transactions
    """
    docFactory = loaders.xmlfile(RESOURCE("templates/Summary"))
    # jsClass = u'Afloat.Summary'

    def __init__(self, service, *a, **kw):
        self.service = service
        super(Summary, self).__init__(*a, **kw)

    @page.renderer
    def summary(self, req, tag):
        pg = tag.patternGenerator('balance')
        content = []
        for account in self.service.store.find(database.Account):
            pat = pg()
            pat.fillSlots('accountType', account.type)
            pat.fillSlots('ledger', '%.2f' % (account.ledgerBalance/100.,))
            pat.fillSlots('available', '%.2f' % (account.availableBalance/100.,))
            content.append(pat)
        return tag[content]


class Graphs(athena.LiveElement):
    """
    The graph showing balance and predicted balance
    """
    docFactory = loaders.xmlfile(RESOURCE("templates/Graphs"))
    jsClass = u'Afloat.Graphs'
    def __init__(self, service, accounts, *a, **kw):
        self.service = service
        self.accounts = accounts
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


class Scheduler(athena.LiveElement):
    """
    User interface for adding new future transactions
    """
    docFactory = loaders.xmlfile(RESOURCE("templates/Scheduler"))
    # jsClass = u'Afloat.Scheduler'
    def __init__(self, service, *a, **kw):
        self.service = service
        super(Scheduler, self).__init__(*a, **kw)

    @page.renderer
    def scheduled(self, req, tag):
        pg = tag.patternGenerator("upcomingItems")
        ss = self.service
        coming = database.scheduledNext3Weeks(ss.store, ss.defaultAccount)
        for item in coming:
            pat = pg()
            pat.fillSlots('amount', '%.2f' % (item.amount/100.,))
            pat.fillSlots('memo', item.title)
            pat.fillSlots('date', item.expectedDate.strftime('%a %m/%d'))
            tag[pat]
        return tag


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
        return AfloatPage(self.service)

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


