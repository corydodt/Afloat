"""
The Service which is started by twistd
"""
import datetime

from twisted.python import log
from twisted.application import internet
from twisted.internet import reactor, task, defer

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

        self.downloadTimes = []
        for timestr in self.config['downloadTimes']:
            t = datetime.datetime.strptime(timestr, '%H:%M').time()
            self.downloadTimes.append(t)

        # start a loopingCall which checks whether it's time yet to download
        self.periodicallyDownload()

        internet.TCPServer.startService(self, *a, **kw)

    def periodicallyDownload(self, ):
        """
        Check when we should download, and if it is time, download
        """
        def checkTime():
            t = datetime.datetime.today().time()
            for dl in self.downloadTimes:
                if (dl.hour, dl.minute) == (t.hour, t.minute):
                    self.doRequests()

        lc = task.LoopingCall(checkTime)

        lc.start(60, now=False)

    def doRequests(self):
        """
        Run all the network requests for OFX data and gvents
        """
        c = self.config
        self.defaultAccount = c['defaultAccount']

        # set up requests for event and bank data retrieval
        from afloat.ofx import get

        getter = get.Options()
        getter.update(self.config)

        from afloat import database

        # keep these processes from being garbage collected
        self._ofxDeferred = database.getOfx(self.store, getter.doGetting,
                **{'encoding': c['encoding']})
        self._gventDeferred = database.getGvents(self.store,
                email=c['gventEmail'], 
                password=c['gventPassword'], 
                calendar=c['gventCalendar'],
                account=c['defaultAccount'],
                )

        # store the results, successful or not, in the database

        def logSuccess(_, service):
            database.NetworkLog.log(self.store, service, u'OK', u'Success')

        def logFailure(f, service):
            log.msg("** Logging to the database: Service %s failed" %
                    (service,) )
            database.NetworkLog.log(self.store, service, u'ERROR',
                    unicode(f))
            log.err(f)

        self._ofxDeferred.addCallback(logSuccess, u'ofx')
        self._ofxDeferred.addErrback(logFailure, u'ofx')
        self._ofxDeferred.addErrback(log.err)

        self._gventDeferred.addCallback(logSuccess, u'gvent')
        self._gventDeferred.addErrback(logFailure, u'gvent')
        self._gventDeferred.addErrback(log.err)

        self._requestsDone = defer.DeferredList([self._ofxDeferred,
            self._gventDeferred,], fireOnOneErrback=True)
        # TODO  self._requestsDone.addCallback(database.matchup)

