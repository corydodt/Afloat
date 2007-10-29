"""
Web resources
"""

from zope.interface import implements

from nevow import rend, static, url, inevow, vhost, athena, loaders, page

from afloat.util import RESOURCE
from afloat import database


class AfloatPage(athena.LivePage):
    docFactory = loaders.xmlfile(RESOURCE('templates/afloatpage.xhtml'))
    addSlash = 1
    def __init__(self, service, *a, **kw):
        self.service = service
        super(AfloatPage, self).__init__(*a, **kw)
    
    def render_all(self, ctx, data):
        summary = Summary(self.service)
        summary.setFragmentParent(self)

        graph = Graph(self.service)
        graph.setFragmentParent(self)

        scheduler = Scheduler(self.service)
        scheduler.setFragmentParent(self)

        return ctx.tag[summary, graph, scheduler]


class Summary(athena.LiveElement):
    """
    Summary at the top showing balances, hover to show holds or big
    transactions
    """
    docFactory = loaders.xmlfile(RESOURCE("elements/Summary"))
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


class Graph(athena.LiveElement):
    """
    The graph showing balance and predicted balance
    """
    docFactory = loaders.xmlfile(RESOURCE("elements/Graph"))
    # jsClass = u'Afloat.Graph'
    def __init__(self, service, *a, **kw):
        self.service = service
        super(Graph, self).__init__(*a, **kw)


class Scheduler(athena.LiveElement):
    """
    User interface for adding new future transactions
    """
    docFactory = loaders.xmlfile(RESOURCE("elements/Scheduler"))
    # jsClass = u'Afloat.Scheduler'
    def __init__(self, service, *a, **kw):
        self.service = service
        super(Scheduler, self).__init__(*a, **kw)


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


