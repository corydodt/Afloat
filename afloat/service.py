"""
The Service which is started by twistd
"""
from twisted.python import log
from twisted.application import internet
from twisted.internet import reactor

from nevow import appserver

from afloat.util import RESOURCE

class STFUSite(appserver.NevowSite):
    """Website with <80 column logging"""
    def log(self, request):
        uri = request.uri

        if 'jsmodule' in uri:
            uris = uri.split('/')
            n = uris.index('jsmodule')
            uris[n-1] = uris[n-1][:3] + '...'
            uri = '/'.join(uris)

        if len(uri) > 38:
            uri = '...' + uri[-35:]

        code = request.code
        if code != 200:
            code = '!%s!' % (code, )

        log.msg('%s %s' % (code, uri), system='HTTP', )


class AfloatService(internet.TCPServer):
    def startService(self, *a, **kw):
        from afloat import database
        self.store = database.initializeStore()

        # load config from config.py
        self.config = {}
        execfile(RESOURCE('../config.py'), self.config)

        # FIXME - reactor.callWhenRunning(self.doRequests) should work here,
        # but somehow self.doRequests still gets called before the reactor is
        # running
        reactor.callLater(0, self.doRequests)

        # TODO - loopingCall to do them in the future

        internet.TCPServer.startService(self, *a, **kw)

    def doRequests(self):
        """
        Run all the network requests for OFX files and gvents
        """
        c = self.config

        # set up requests for event and bank data retrieval
        from afloat.ofx import get
        from afloat import database
        rq1 = get.accountInfoRequest(user=c['user'],
                password=c['password'], fid=c['fid'], bank=c['bank'],
                org=c['org'], url=c['url'])

        requests = [ rq1 ]
        for accountNum, accountType in c['accounts'].items():
            rq = get.statementRequest(user=c['user'],
                    password=c['password'], fid=c['fid'], bank=c['bank'],
                    org=c['org'], url=c['url'], account=accountNum,
                    accountType=accountType)
            requests.append(rq)
        # keep these processes from being garbage collected
        self._ofxDeferred = database.getOfx(self.store, *requests,
                **{'ofxEncoding': c['ofxEncoding']})
        self._gventsDeferred = database.getGvents(self.store)


