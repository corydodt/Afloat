import sys, os
import re
import datetime
import md5

from twisted.python import usage

import atom
from gdata.calendar.service import CalendarEventQuery, CalendarService
from gdata import calendar

from afloat.util import RESOURCE, days

CALENDAR_NAMES = {
        'finance': 'bd7j228bhdt527n0o4pk8dhf50@group.calendar.google.com'
}

AFLOAT_NS = 'http://thesoftworld.com/2007/afloat#'

AFLOAT_USERAGENT = 'TheSoftWorld-Afloat-0.0'

def uu(key):
    """
    A short uuid for google events keys
    """

    ret = '%s-%s' % (md5.md5(AFLOAT_NS + key).hexdigest(), key)
    assert len(ret) < 45, "Google extended_property keys cannot be that long: %s" % (ret,)
    return ret

# afloat#paid ; value: a datetime that indicates when it was paid
EVENT_PAID = uu('paid')
# afloat#bankId ; value: a string that matches a bank trnid
EVENT_BANKID = uu('bankId')
# afloat#originalDate ; value: a datetime that indicates the user-entered date
EVENT_ORIGINALDATE = uu('origDate')
# afloat#amount ; value: an integer (cents.. divide by 100 for dollars)
EVENT_AMOUNT = uu('amount')
# afloat#fromAccount ; value: string account number
EVENT_FROMACCOUNT = uu('fromAcct')
# afloat#toAccount ; value: string account number
EVENT_TOACCOUNT = uu('toAcct')
# afloat#checkNumber ; value: string account number
EVENT_CHECKNUMBER = uu('checkNum')


class NoAmountError(Exception):
    pass


class MissingToAccount(Exception):
    """
    An event that needed a To account didn't have one.  Events without any to
    or from are defaulted to checking; this gets raised ONLY if an event with
    a From account doesn't have a To account.
    """


def deleteExactEvent(client, uri):
    """
    Remove the event.  Returns nothing
    """
    client.DeleteEvent(uri)

def getExactEvent(client, uri):
    return client.GetCalendarEventEntry(uri)

def dateQuery(client, calendarName, start_date, end_date, **kwargs):
    """
    Retrieves events from the server which occur during the specified date
    range.

    **kwargs may be specified to enhance the query
    """
    query = CalendarEventQuery(calendarName, 'private', 'full')
    query.update(kwargs)
    query.start_min = start_date
    query.start_max = end_date
    return client.CalendarQuery(query)

def deleteEvent(client, event):
    """
    Given an event object returned for the calendar server, this method
    deletes the event.  The edit link present in the event is the URL used
    in the HTTP DELETE request.
    """
    client.DeleteEvent(event.GetEditLink().href)

def quickAddEvent(client, calendarName, content="Tennis with John today 3pm-3:30pm"):
    """
    Creates an event with the quick_add property set to true so the content
    is processed as quick add content instead of as an event description.
    """
    event = calendar.CalendarEventEntry()
    event.content = atom.Content(text=content)
    event.quick_add = calendar.QuickAdd(value='true');

    new_event = client.InsertEvent(event,
        '/calendar/feeds/%s/private/full' % (calendarName,))
    return new_event

def _copyEventCommon(event):
    """
    Create new event as a copy of 'event', only copying things that always
    need to be copied
    """
    new1 = calendar.CalendarEventEntry()
    new1.author = event.author
    new1.category = event.category
    new1.comments = event.comments
    new1.content = event.content
    new1.contributor = event.contributor
    new1.control = event.control
    new1.event_status = event.event_status
    new1.extended_property = event.extended_property
    new1.original_event = event.original_event
    new1.published = event.published
    new1.recurrence = event.recurrence
    new1.rights = event.rights
    new1.source = event.source
    new1.summary = event.summary
    new1.text = event.text
    new1.title = event.title
    new1.transparency = event.transparency
    new1.updated = event.updated
    new1.visibility = event.visibility
    new1.when = event.when
    new1.where = event.where
    new1.who = event.who
    return new1

def copyEventForScrub(client, calendarName, event):
    """
    Copy an event to a duplicate event, keeping recurrence and original_event,
    then insert it into the calendar.

    This copies everything except extended_property.
    """
    new1 = _copyEventCommon(event)
    new1.extended_property = None
    return client.InsertEvent(new1,
        '/calendar/feeds/%s/private/full' % (calendarName,))

def cloneAsException(client, calendarName, event, when):
    """
    Create an exception event for 'event', an INSTANCE of a recurring event,
    using 'when' as the destination times and creating an OriginalEvent.

    This copies everything except when, recurrence and original_event.

    Insert and then return the clone.
    """
    assert event.recurrence is not None
    
    new1 = _copyEventCommon(event)
    # OriginalEvent is supposed to refer to the when of the original event.
    # that is, when the recurring event WOULD have occurred naturally.
    orig = calendar.OriginalEvent(id=event.id.text, when=event.when)
    new1.original_event = orig
    new1.recurrence = None
    # THIS when refers to the new time, now that we have rescheduled.
    new1.when = when
    ev = client.InsertEvent(new1,
        '/calendar/feeds/%s/private/full' % (calendarName,))
    return ev

def formatEventString(event):
    e = event
    eProps = {}
    for prop in e.extended_property:
        eProps[prop.name] = prop.value
    get = lambda k: eProps.get(k)
    href = e.GetSelfLink().href

    ret = []
    for when in e.when:
        ret.append(
                str(CalendarEventString(href,
                    e.title.text,
                    get(EVENT_PAID),
                    get(EVENT_BANKID),
                    get(EVENT_CHECKNUMBER),
                    get(EVENT_ORIGINALDATE),
                    when.start_time,
                    get(EVENT_AMOUNT),
                    get(EVENT_FROMACCOUNT),
                    get(EVENT_TOACCOUNT),
                    )
                )
            )

    return '\n'.join(ret)

def dateRange(d1, d2):
    """
    Return a series of dates between two dates, including both ends
    (this is an asymmetry with the builtin range() function for example)
    """
    assert d2 > d1, "End date must be later than start date"
    start = parseDateYMD(d1)
    end = parseDateYMD(d2)
    ret = [start]
    last = ret[-1]
    while last < end:
        last = last + days(1)
        ret.append(last)

    return ret

def findAccounts(s):
    """
    Return the from,to accounts
    """
    for line in s.splitlines():
        if re.match(r'^[a-zA-Z0-9]+->[a-zA-Z0-9]+$', line):
            ret = [x.strip() for x in line.split('->')]
            return ret
    return [None, None]


# functions for parsing the content of a calendar entry
dollarRx = re.compile(r'^\$-?[0-9]+(\.[0-9]+)?$')
noDollarRx = re.compile(r'^-?[0-9]+(\.[0-9]+)?$')

def findAmount(s):
    """
    In a string, find numeric or monetary tokens, and return the one most
    likely to be a money amount.
    Return the amount in whole cents.
    """
    words = s.split()
    for word in words:
        if dollarRx.match(word):
            return int(float(word.strip('$'))*100)
    for word in words:
        if noDollarRx.match(word):
            return int(float(word)*100)

checkRx = re.compile(r'#\d+\b')

def findCheckNumber(s):
    """
    Return the check number if any
    """
    words = s.split()
    for word in words:
        if checkRx.match(word):
            return word

bracketRx = re.compile(r'\[.*?\]')

def cleanEventTitle(event):
    """
    Remove comments, in brackets
    """
    return bracketRx.sub('', event.title.text)


def fixupEvent(client, event):
    """
    Parse numerics in event's title and set extended amount attribute on
    event.  Parse from/to fields from event description and get From/To for a
    transaction.
    Do nothing if event already has these attributes.
    If anything changed, send the event back to Google.
    """
    assert not event.recurrence, (
            "Called fixupEvent on recurring: %s" % (event.title.text,))

    changed = 0

    propsFound = dict([(x.name, x.value) for x in event.extended_property])
    get = propsFound.get


    # remove [comments inside brackets] before processing the event
    titleText = cleanEventTitle(event)


    # add amount properties by parsing the title
    amount = findAmount(titleText)
    if amount is None:
        raise NoAmountError(titleText)

    if get(EVENT_AMOUNT) != amount or EVENT_AMOUNT not in propsFound:
        prop = calendar.ExtendedProperty(name=EVENT_AMOUNT, value=str(amount))
        event.extended_property.append(prop)
        propsFound[EVENT_AMOUNT] = prop.value
        changed = 1


    # add check number properties by parsing the title
    cn = findCheckNumber(titleText)
    if get(EVENT_CHECKNUMBER) != cn or EVENT_CHECKNUMBER not in propsFound:
        if cn is not None:
            prop = calendar.ExtendedProperty(name=EVENT_CHECKNUMBER, value=str(cn))
            event.extended_property.append(prop)
            propsFound[EVENT_CHECKNUMBER] = prop.value
            changed = 1
    ## else: ...
    ## FIXME - retitling an event, such that there is no longer a check
    ## number, should clear the check number property.
    ## But there is presently no way to simply remove an extended_property
    ## from a google event, so we can't handle this case


    # add account properties by parsing the event.content.text
    if event.content.text:
        fromAccount, toAccount = findAccounts(event.content.text)
        if ( (get(EVENT_TOACCOUNT) != toAccount) or
             (get(EVENT_FROMACCOUNT) != fromAccount)
             ) and event.content.text:
            if toAccount is not None:
                prop = calendar.ExtendedProperty(name=EVENT_TOACCOUNT,
                        value=toAccount.upper().strip())
                event.extended_property.append(prop)
                changed = 1
            if fromAccount is not None:
                if toAccount is None:
                    raise MissingToAccount(event)
                prop = calendar.ExtendedProperty(name=EVENT_FROMACCOUNT,
                        value=fromAccount.upper().strip())
                event.extended_property.append(prop)
                changed = 1
    ## else: ...
    ## FIXME - clearing event.content.text in google calendar should also
    ## clear from/to accounts.
    ## But there is presently no way to simply remove an extended_property
    ## from a google event, so we can't handle this case


    # add original date property by looking at event.when
    E_OD = EVENT_ORIGINALDATE
    w = event.when[0]
    if get(E_OD) != w.start_time or E_OD not in propsFound:
        prop = calendar.ExtendedProperty(name=E_OD, value=w.start_time)
        event.extended_property.append(prop)
        propsFound[E_OD] = prop.value
        changed = 1


    # done. save to google.
    if changed:
        client.UpdateEvent(event.GetEditLink().href, event)

    return event


class CalendarEventString(object):
    """
    A marshallable, trivially parseable form of a calendar event
    """
    def __init__(self, href, title, paidDate, bankId, checkNumber,
            originalDate, expectedDate, amount, fromAccount, toAccount, ):
        coalesce = lambda x: (None if not x else unicode(x))

        self.href = unicode(href)
        self.title = unicode(title)
        self.paidDate = parseDateYMD(paidDate)
        if checkNumber is not None:
            self.checkNumber = int(checkNumber.lstrip('#'))
        else:
            self.checkNumber = None
        self.bankId = coalesce(bankId)

        assert originalDate is not None

        self.originalDate = parseDateYMD(originalDate[:10])
        self.expectedDate = parseDateYMD(expectedDate[:10])
        self.amount = int(amount)
        self.fromAccount = coalesce(fromAccount)
        self.toAccount = coalesce(toAccount)

    def __str__(self):
        ret = "%s %s %s %s %s %s %s %s %s %s" % (
            self.href,
            re.sub('\s+', '+', self.title),
            formatDateYMD(self.paidDate) or '~',
            self.bankId or '~',
            self.checkNumber or '~',
            formatDateYMD(self.originalDate),
            formatDateYMD(self.expectedDate),
            self.amount,
            self.fromAccount or '~',
            self.toAccount or '~',
            )
        return ret

    @classmethod
    def fromString(cls, s):
        splits = s.split()
        href, title, paidDate, bankId, checkNumber, originalDate, expectedDate, amount, fromAccount, toAccount = splits

        parseTilde = lambda x: (None if x == '~' else x)

        new1 = cls( href,
                ' '.join(title.split('+')),
                parseTilde(paidDate),
                parseTilde(bankId),
                parseTilde(checkNumber),
                originalDate,
                expectedDate,
                amount,
                parseTilde(fromAccount),
                parseTilde(toAccount),
                )
        return new1


class GetEvents(usage.Options):
    """
    Print the events as a list of them, fields separated by spaces
    """
    optFlags = [['fixup', 'f', 'Do the fixup step, adding metadata to '
        'calendar items that do not have it'],
        ['show-unclean', None, 'Show events that have extended properties',],
    ]
    def parseArgs(self, date1=None, date2=None):
        # date1 and date2 may be missing, if environment variable is set
        if not all([date1, date2]):
            dates = os.environ.get('READCAL_DATES')
            if dates:
                try:
                    e_date1, e_date2 = dates.strip().split()
                except ValueError:
                    raise usage.UsageError("** READCAL_DATES was set incorrectly. "
                            "Should be two dates, separated by a space")
                if not date1:
                    date1 = e_date1
                if not date2:
                    date2 = e_date2
            else:
                raise usage.UsageError("** Must specify dates or set "
                        "READCAL_DATES in the environment")
        execfile(RESOURCE('../config.py'), self)
        self['dateStart'] = date1
        self['dateEnd'] = date2

    def postOptions(self):
        self.update(self.parent)

        d1 = self['dateStart']
        d2 = self['dateEnd']

        # connect and pull all the events from google calendar
        client = connectClient(**self)
        feed = self.getEvents(client, d1, d2)

        # process each event according to command-line options
        for e in feed.entry:
            # show events that have any extended properties (these have had
            # fixup done on them at some point in the past)
            if self['show-unclean']:
                if e.extended_property:
                    h = e.GetEditLink().href.split('/')[-1]
                    print >> sys.stderr, e.title.text, '.../' + h
                    print >> sys.stderr, '  ', '  \n  '.join([
                            '%s %s' % (x.name, x.value) 
                            for x in e.extended_property])
                continue

            # fixup events if dictated
            if self['fixup']:
                try:
                    e = fixupEvent(client, e)
                except NoAmountError:
                    # missing amount -> not a real event, don't even attempt
                    # to handle it
                    continue

            formatted = formatEventString(e)
            if formatted:
                print formatted

    def getEvents(self, client, date1, date2):
        return dateQuery(client, self['gventCalendar'], date1, date2, 
                singleevents='true', orderby='starttime')


class ScrubEvents(GetEvents):
    """
    Remove all events and re-insert them without extended properties
    """
    optFlags = []
    def parseArgs(self, date1, date2):
        execfile(RESOURCE('../config.py'), self)
        self['dateStart'] = date1
        self['dateEnd'] = date2

    def postOptions(self):
        self.update(self.parent)

        d1 = self['dateStart']
        d2 = self['dateEnd']

        # connect and pull all the events from google calendar
        client = connectClient(**self)
        feed = self.getEvents(client, d1, d2)

        # process each event according to command-line options
        for e in feed.entry:
            if e.extended_property:
                self.scrubEvent(client, e)

    def scrubEvent(self, client, event):
        """
        Replace an event.  Keep all when, title, and body attributes.  Do
        not set any extended properties.
        """
        if event.original_event:
            return
        new1 = copyEventForScrub(client, self['gventCalendar'], event)
        deleteEvent(client, event)


class AddEvent(usage.Options):
    """
    Add a single event.  Return 'OK' when successful.
    
    (This does NOT print the new event, because it might require creating
    recurrence exceptions, and we don't have any idea what the range of the
    exceptions should be.)
    """
    optFlags = []
    def parseArgs(self, content ):
        execfile(RESOURCE('../config.py'), self)
        self['content'] = content

    def postOptions(self):
        self.update(self.parent)

        # connect and pull all the events from google calendar
        client = connectClient(**self)
        _ = self.addEvent(client)
        print 'OK'

    def addEvent(self, client):
        ev = quickAddEvent(client, self['gventCalendar'], self['content'])
        return ev


class RemoveEvent(usage.Options):
    """
    Remove a single event
    """
    optFlags = []
    def parseArgs(self, uri):
        execfile(RESOURCE('../config.py'), self)
        self['uri'] = uri

    def postOptions(self):
        self.update(self.parent)

        # connect and pull all the events from google calendar
        client = connectClient(**self)
        print self.removeEvent(client)

    def removeEvent(self, client):
        ev = getExactEvent(client, self['uri'])

        assert not ev.recurrence, "Cannot delete a recurring event"

        deleteExactEvent(client, ev.GetEditLink().href)

        return formatEventString(ev)


def connectClient(gventPassword, gventEmail, **kw):
    """
    Return a new client instance, already logged in
    """
    client = CalendarService()
    client.password = gventPassword
    client.email = gventEmail
    client.source = AFLOAT_USERAGENT
    client.ProgrammaticLogin()
    return client


class UpdateEvent(usage.Options):
    """
    Update an event per the command-line options
    """
    optFlags = []
    optParameters = [
            ['paidDate', None, None, 'Change the paidDate',],
            ['amount', None, None, 'Change the amount',],
            ['title', None, None, 'Change the title',],
            ['expectedDate', None, None, 'Change the expectedDate',],
            ['originalDate', None, None, 'Change the originalDate',],
            ]
    def parseArgs(self, uri):
        execfile(RESOURCE('../config.py'), self)
        self['uri'] = uri

    def postOptions(self):
        self.update(self.parent)

        # connect and pull all the events from google calendar
        client = connectClient(**self)
        print self.updateEvent(client)

    def updateEvent(self, client):
        ev = getExactEvent(client, self['uri'])

        assert not ev.recurrence, "Cannot update a recurring event!"

        changed = 0

        if self['paidDate']:
            prop = calendar.ExtendedProperty(name=EVENT_PAID, 
                    value=self['paidDate'])
            ev.extended_property.append(prop)
            changed = 1

        if self['amount']:
            prop = calendar.ExtendedProperty(name=EVENT_AMOUNT, 
                    value=self['amount'])
            ev.extended_property.append(prop)
            changed = 1

        if self['expectedDate']:
            start = parseDateYMD(self['expectedDate'])
            end = start + days(1)
            ev.when[0].start_time = self['expectedDate']
            ev.when[0].end_time = formatDateYMD(end)
            changed = 1

        if self['originalDate']:
            prop = calendar.ExtendedProperty(name=EVENT_ORIGINALDATE,
                    value=self['originalDate'])
            ev.extended_property.append(prop)
            changed = 1

        if self['title']:
            ev.title.text = self['title']
            changed = 1

        if changed:
            client.UpdateEvent(ev.GetEditLink().href, ev)

        return formatEventString(ev)


def formatDateYMD(dt):
    if dt is None:
        return None
    return dt.strftime('%Y-%m-%d')


def parseDateYMD(s):
    """
    Return a datetime from a nnnn-nn-nn format date
    """
    if s is None:
        return None
    return datetime.datetime.strptime(s, '%Y-%m-%d')


def parseKeywords(s):
    """
    Split into keywords, removing check numbers and money amounts
    """
    words = s.split()
    retWords = dict(enumerate(words))

    # check first for anything with a $ as the amount.
    # if that doesn't work, then check for any number as the amount.
    # if we found an amount, remove it.
    foundAmount = 0
    for n, word in retWords.items():
        if dollarRx.match(word) and not foundAmount:
            foundAmount = 1
            del retWords[n]
        if checkRx.match(word):
            del retWords[n]

    if not foundAmount:
        for n, word in retWords.items():
            if noDollarRx.match(word):
                foundAmount = 1
                del retWords[n]
                break

    return zip(*sorted(retWords.items()))[1]


class Options(usage.Options):
    synopsis = "readcal <subcommand>"
    subCommands = [
        ['get-events', None, GetEvents, 'Get all events in given date range'],
        ['scrub-events', None, ScrubEvents, 'Remove extended properties from events in range'],
        ['add-event', None, AddEvent, 'Add an event using quick-add'],
        ['remove-event', None, RemoveEvent, 'Remove an event - TODO - break recurrence if necessary'],
        ['update-event', None, UpdateEvent, 'Update an event - TODO - break recurrence if necessary'],
    ]
    optParameters = [ ]

    def postOptions(self):
        if not self.subCommand:
            raise usage.UsageError('** Please give a sub-command')


def run(argv=None):
    if argv is None:
        argv = sys.argv
    o = Options()
    try:
        o.parseOptions(argv[1:])
    except usage.UsageError, e:
        print str(o)
        print str(e)
        return 1

    return 0


if __name__ == '__main__': sys.exit(run())
