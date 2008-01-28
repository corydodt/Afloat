"""
The Service which is started by twistd
"""
import datetime

from twisted.python import log
from twisted.application import internet
from twisted.internet import reactor, task

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

        self.readConfig()

        self.report = database.AfloatReport(self.store, self.config)

        # FIXME - reactor.callWhenRunning(self.doRequests) should work here,
        # but somehow self.doRequests still gets called before the reactor is
        # running
        reactor.callLater(0, self.report.update)

        self.downloadTimes = []
        for timestr in self.config['downloadTimes']:
            t = datetime.datetime.strptime(timestr, '%H:%M').time()
            self.downloadTimes.append(t)

        # start a loopingCall which checks whether it's time yet to download
        self.periodicallyDownload()

        internet.TCPServer.startService(self, *a, **kw)

    def readConfig(self):
        """
        Load config from config.py and do any massaging necessary.
        """
        c = self.config = {}
        execfile(RESOURCE('../config.py'), self.config)

        ahead = int(c['lookAheadDays'])
        if not (4 <= ahead <= 30):
            c['lookAheadDays'] = min([30, max([4, ahead])])
            log.msg("** WARNING: lookAheadDays must be between 4 and 30."
                " Adjusted to %s" % (c['lookAheadDays'],))

        behind = int(c['lookBehindDays'])
        if not (4 <= behind <= 30):
            c['lookBehindDays'] = min([30, max([4, behind])])
            log.msg("** WARNING: lookBehindDays must be between 4 and 30."
                " Adjusted to %s" % (c['lookBehindDays'],))

    def periodicallyDownload(self, ):
        """
        Check when we should download, and if it is time, download
        """
        def checkTime():
            t = datetime.datetime.today().time()
            for dl in self.downloadTimes:
                if (dl.hour, dl.minute) == (t.hour, t.minute):
                    self.report.update()

        lc = task.LoopingCall(checkTime)

        lc.start(60, now=False)
