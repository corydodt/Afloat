"""
Process Protocol for communicating with readcal through stdio
"""
import os

from twisted.internet.protocol import ProcessProtocol
from twisted.internet.error import ProcessDone
from twisted.internet import reactor, defer
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

    def errReceived(self, data):
        self.errors = self.errors + data

    def processEnded(self, reason):
        """Notify our disconnects"""
        print '** ending process'
        if self.errors:
            log.msg('*** readcal errored out ***', self.errors)
            for d in self.disconnectDeferreds:
                d.errback(reason)
        else:
            for d in self.disconnectDeferreds:
                d.callback(reason)
        print '** ended process'

    def notifyOnDisconnect(self):
        d = defer.Deferred()
        self.disconnectDeferreds.append(d)
        return d


class GVentProtocolSimple(GVentProtocol):
    """
    A version of GVentProtocol which does not try to parse gvents
    """
    def outReceived(self, data):
        self.stream = self.stream + data


def pythonProcessRunner(proto, after, *afterArgs, **afterKwargs):
    """
    Decorate a function that returns command line arguments with another
    function that actually runs python, with spawnProcess, using those command
    line arguments.

    @arg after: A callback function that will return the desired result from
    the process after it runs.  It will be called back with an instance of
    GVentProtocol after the process runs.

    @arg afterArgs, afterKwargs: These will be appended to the parameter list
    of after, as arguments.
    """
    def runner(fn):
        def decorated(*fna, **fnkw):
            processArgs = fn(*fna, **fnkw)
            print '** In pythonProcessRunner: .. ', ' '.join(processArgs)
            pp = proto()
            pTransport = reactor.spawnProcess(pp, '/usr/bin/python', processArgs,
                    env=os.environ, usePTY=0)
            print '** spawned process'
            d_ = pp.notifyOnDisconnect()

            def cleanProcessDone(reason, pp):
                """
                Ignore ProcessDone
                """
                print '** cleanup after process'
                reason.trap(ProcessDone)
                return pp

            d_.addErrback(cleanProcessDone, pp)
            d_.addCallback(after, *afterArgs, **afterKwargs)
            print '** returning from', fn
            return d_
        return decorated
    return runner


@pythonProcessRunner(GVentProtocol, lambda pp: pp.gvents)
def getGvents(date1, date2):
    """
    Utility fn to retrieve gvents and return them as CalendarEventString
    objects
    """
    pp = GVentProtocol()
    date1 = date1.strftime('%Y-%m-%d')
    date2 = date2.strftime('%Y-%m-%d')

    args = ['python', '-m', 'afloat.gvent.readcal',
         'get-events', '--fixup', date1, date2,
        ]
    return args


@pythonProcessRunner(GVentProtocol, lambda pp: pp.gvents[0])
def remove(href):
    """
    Utility fn to un-schedule an event
    """
    args = ['python', '-m', 'afloat.gvent.readcal',
         'remove-event', href]
    return args


@pythonProcessRunner(GVentProtocolSimple, lambda pp: 'OK')
def quickAdd(content):
    """
    Utility fn to schedule a new event with the quick add interface
    and return a CalendarEventString with the new event
    """
    args = ['python', '-m', 'afloat.gvent.readcal',
         'add-event', content]
    return args


@pythonProcessRunner(GVentProtocol, lambda pp: pp.gvents[0])
def putMatchedTransaction(uri, paidDate, expectedDate, newAmount, newTitle):
    """
    Utility fn to send a transaction back to google with post-matchup fixes,
    and return a CalendarEventString with the changes
    """
    args = ['python', '-m', 'afloat.gvent.readcal',
         'update-event', 
         '--paidDate=%s' % (formatDateYMD(paidDate),),
         '--expectedDate=%s' % (formatDateYMD(expectedDate),),
         '--amount=%s' % (newAmount,), 
         '--title=%s' % (str(newTitle),),
         str(uri), 
        ]
    return args


@pythonProcessRunner(GVentProtocol, lambda pp: pp.gvents[0])
def changeDate(uri, newDate, original=True):
    """
    Change the date on a scheduled transaction.  When original=True, change
    the originalDate as well as the expectedDate
    """
    dt = formatDateYMD(newDate)
    args = ['python', '-m', 'afloat.gvent.readcal',
         'update-event', 
         '--expectedDate=%s' % (dt,),
         '--originalDate=%s' % (dt,),
         str(uri), 
        ]
    return args
