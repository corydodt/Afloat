"""
Process Protocol for communicating with readcal through stdio
"""
import os

from twisted.internet.protocol import ProcessProtocol
from twisted.internet.error import ProcessDone
from twisted.internet import reactor, defer
from twisted.python.text import stringyString
from twisted.python import log

from afloat.gvent.readcal import CalendarEventString, formatDateYMD

class GVentProtocol(ProcessProtocol):
    """
    Communicate with "python afloat/gvent/readcal.py ..." to retrieve the calendar
    items on stdout
    """
    TERM = '\n'
    def __init__(self, *a, **kw):
        self.stream = ''
        self.errors = ''
        self.gvents = []
        self.disconnectDeferreds = []

    def streamEndsWith(self, s):
        chars = len(s)
        self.stream.seek(-chars, 2)
        tail = self.stream.read()
        return tail == s

    def loadEventFromStream(self):
        """
        Load the last entire event from the stream
        """
        termPos = self.stream.find(self.TERM)
        while termPos >= 0:
            item = self.stream[:termPos]
            event = CalendarEventString.fromString(item)
            self.gvents.append(event)
            self.stream = self.stream[termPos + len(self.TERM):]
            termPos = self.stream.find(self.TERM)

    def outReceived(self, data):
        self.stream = self.stream + data
        if self.TERM in self.stream:
            self.loadEventFromStream()
            g = self.gvents[-1]

    def errReceived(self, data):
        self.errors = self.errors + data

    def processEnded(self, reason):
        """Notify our disconnects"""
        if self.errors:
            log.msg('*** readcal errored out ***', self.errors)
            for d in self.disconnectDeferreds:
                d.errback(reason)
                return
        for d in self.disconnectDeferreds:
            d.callback(reason)

    def notifyOnDisconnect(self):
        d = defer.Deferred()
        self.disconnectDeferreds.append(d)
        return d


def getGvents(date1, date2):
    """
    Utility function to retrieve gvents and return them as CalendarEventString
    objects
    """
    pp = GVentProtocol()
    date1 = date1.strftime('%Y-%m-%d')
    date2 = date2.strftime('%Y-%m-%d')

    args = ['python', '-m', 'afloat.gvent.readcal',
         'get-events', '--fixup', date1, date2,
        ]
    print ' '.join(args)
    pTransport = reactor.spawnProcess(pp, '/usr/bin/python', args,
            env=os.environ, usePTY=0)

    def cleanProcessDone(reason, pp):
        """
        Ignore ProcessDone
        """
        reason.trap(ProcessDone)
        return pp.gvents

    d_ = pp.notifyOnDisconnect()
    d_.addErrback(cleanProcessDone, pp)
    d_.addCallback(lambda _: pp.gvents)
    return d_


def remove(href):
    """
    Utility fn to un-schedule an event
    """
    pp = GVentProtocol()

    args = ['python', '-m', 'afloat.gvent.readcal',
         'remove-event', href]
    print ' '.join(args)
    pTransport = reactor.spawnProcess(pp, '/usr/bin/python', args,
            env=os.environ, usePTY=0)

    def cleanProcessDone(reason, pp):
        """
        Ignore ProcessDone
        """
        reason.trap(ProcessDone)
        return pp.gvents

    d_ = pp.notifyOnDisconnect()
    d_.addErrback(cleanProcessDone, pp)
    d_.addCallback(lambda _: pp.gvents[0])
    return d_


def quickAdd(content):
    """
    Utility fn to schedule a new event with the quick add interface
    and return a CalendarEventString with the new event
    """
    pp = GVentProtocol()

    args = ['python', '-m', 'afloat.gvent.readcal',
         'add-event', content]
    print ' '.join(args)
    pTransport = reactor.spawnProcess(pp, '/usr/bin/python', args,
            env=os.environ, usePTY=0)

    def cleanProcessDone(reason, pp):
        """
        Ignore ProcessDone
        """
        reason.trap(ProcessDone)
        return pp.gvents

    d_ = pp.notifyOnDisconnect()
    d_.addErrback(cleanProcessDone, pp)
    d_.addCallback(lambda _: pp.gvents[0])
    return d_


def putMatchedTransaction(uri, paidDate, newAmount, newTitle):
    """
    Utility fn to send a transaction back to google with post-matchup fixes,
    and return a CalendarEventString with the changes
    """
    pp = GVentProtocol()

    args = ['python', '-m', 'afloat.gvent.readcal',
         'update-event', 
         '--paidDate=%s' % (formatDateYMD(paidDate),),
         '--amount=%s' % (newAmount,), 
         '--title=%s' % (str(newTitle),),
         str(uri), 
        ]
    print ' '.join(args)
    pTransport = reactor.spawnProcess(pp, '/usr/bin/python', args,
            env=os.environ, usePTY=0)

    def cleanProcessDone(reason, pp):
        """
        Ignore ProcessDone
        """
        reason.trap(ProcessDone)
        return pp.gvents

    d_ = pp.notifyOnDisconnect()
    d_.addErrback(cleanProcessDone, pp)
    d_.addCallback(lambda _: pp.gvents[0])
    return d_
