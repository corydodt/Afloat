import sys
import re
import datetime
import md5

from twisted.python import usage

import atom
from gdata.calendar.service import CalendarEventQuery, CalendarService
from gdata import calendar
from gdata.service import RequestError

from afloat.util import RESOURCE

CALENDAR_NAMES = {
        'finance': 'bd7j228bhdt527n0o4pk8dhf50@group.calendar.google.com'
}

AFLOAT_NS = 'http://thesoftworld.com/2007/afloat#'

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
    return client.DeleteEvent(uri)

def getExactEvent(client, uri):
    return client.GetCalendarEventEntry(uri)

def dateQuery(client, calendarName, start_date, end_date):
    """
    Retrieves events from the server which occur during the specified date
    range.
    """
    query = CalendarEventQuery(calendarName, 'private', 'full')
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

def copyEvent(client, calendarName, event):
    new1 = calendar.CalendarEventEntry()
    new1.author = event.author
    new1.category = event.category
    new1.comments = event.comments
    new1.content = event.content
    new1.contributor = event.contributor
    new1.control = event.control
    new1.event_status = event.event_status
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
    return client.InsertEvent(new1,
        '/calendar/feeds/%s/private/full' % (calendarName,))

def formatEventString(event):
    e = event
    eProps = {}
    for prop in e.extended_property:
        eProps[prop.name] = prop.value
    get = lambda k: eProps.get(k)
    href = e.GetSelfLink().href

    # skip over special events created when you break a recurring
    # event  (??)
    if e.original_event is not None:
        return

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


# functions for parsing the content of a calendar entry
dollarRx = re.compile(r'^\$-?[0-9]+(\.[0-9]+)?$')
noDollarRx = re.compile(r'^-?[0-9]+(\.[0-9]+)?$')
checkRx = re.compile(r'#\d+\b')
bracketRx = re.compile(r'\[.*?\]')

def findAccounts(s):
    """
    Return the from,to accounts
    """
    for line in s.splitlines():
        if re.match(r'^[a-zA-Z0-9]+->[a-zA-Z0-9]+$', line):
            ret = [x.strip() for x in line.split('->')]
            return ret
    return [None, None]

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

def findCheckNumber(s):
    """
    Return the check number if any
    """
    words = s.split()
    for word in words:
        if checkRx.match(word):
            return word


def cleanEventTitle(event):
    return bracketRx.sub('', event.title.text)
    

def fixupEvent(client, event):
    """
    Parse numerics in event's title and set extended amount attribute on
    event.  Parse from/to fields from event description and get From/To for a
    transaction.
    Do nothing if event already has these attributes.
    If anything changed, send the event back to Google.
    """
    changed = 0
    propsFound = dict([(x.name, x.value) for x in event.extended_property])

    get = propsFound.get

    # remove [comments inside brackets] before processing the event
    titleText = cleanEventTitle(event)

    amount = findAmount(titleText)
    if amount is None:
        raise NoAmountError(titleText)

    if get(EVENT_AMOUNT) != amount or EVENT_AMOUNT not in propsFound:
        prop = calendar.ExtendedProperty(name=EVENT_AMOUNT, value=str(amount))
        event.extended_property.append(prop)
        propsFound[EVENT_AMOUNT] = prop.value
        changed = 1

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

    assert len(event.when) == 1
    startTime = event.when[0].start_time
    if get(EVENT_ORIGINALDATE) != startTime or EVENT_ORIGINALDATE not in propsFound:
        # FIXME - just setting this HAS to break recurrence because
        # there will be a separate ORIGINALDATE for each one
        prop = calendar.ExtendedProperty(name=EVENT_ORIGINALDATE,
                value=startTime)
        event.extended_property.append(prop)
        propsFound[EVENT_ORIGINALDATE] = prop.value
        changed = 1

    if changed:
        client.UpdateEvent(event.GetEditLink().href, event)


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
        self.originalDate = parseDateYMD(originalDate)
        self.expectedDate = parseDateYMD(expectedDate)
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
    def parseArgs(self, date1, date2):
        execfile(RESOURCE('../config.py'), self)
        self['dateStart'] = date1
        self['dateEnd'] = date2

    def postOptions(self):
        self.update(self.parent)

        d1 = self['dateStart']
        d2 = self['dateEnd']

        # connect and pull all the events from google calendar
        client = CalendarService()
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
                    fixupEvent(client, e)
                except NoAmountError:
                    pass
                except RequestError:
                    # Instances of recurring events may have cruft and
                    # gremlins. Ignore errors on them.  Raise on others.
                    if e.original_event:
                        continue
                    raise

            # print the event for other programs to parse
            formatted = formatEventString(e)
            if formatted:
                print formatted

    def getEvents(self, client, date1, date2):
        client.password = self['gventPassword']
        client.email = self['gventEmail']
        client.source = 'TheSoftWorld-Afloat-0.0'
        client.ProgrammaticLogin()

        return dateQuery(client, self['gventCalendar'], date1, date2)


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
        client = CalendarService()
        feed = self.getEvents(client, d1, d2)

        # process each event according to command-line options
        for e in feed.entry:
            if e.extended_property:
                # print the event for other programs to parse
                self.scrubEvent(client, e)

    def scrubEvent(self, client, event):
        """
        Replace an event.  Keep all when, title, and body attributes.  Do
        not set any extended properties.
        """
        if event.original_event:
            return
        new1 = copyEvent(client, self['gventCalendar'], event)
        deleteEvent(client, event)


class AddEvent(usage.Options):
    """
    Add a single event
    """
    optFlags = []
    def parseArgs(self, content ):
        execfile(RESOURCE('../config.py'), self)
        self['content'] = content

    def postOptions(self):
        self.update(self.parent)

        # connect and pull all the events from google calendar
        client = CalendarService()
        print self.addEvent(client)

    def addEvent(self, client):
        client.password = self['gventPassword']
        client.email = self['gventEmail']
        client.source = 'TheSoftWorld-Afloat-0.0'
        client.ProgrammaticLogin()

        ev = quickAddEvent(client, self['gventCalendar'], self['content'])

        # always use fixup on new events before formatting them
        fixupEvent(client, ev)

        return formatEventString(ev)


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
        client = CalendarService()
        print self.removeEvent(client)

    def removeEvent(self, client):
        client.password = self['gventPassword']
        client.email = self['gventEmail']
        client.source = 'TheSoftWorld-Afloat-0.0'
        client.ProgrammaticLogin()

        ev = deleteExactEvent(client, self['uri'])

        return formatEventString(ev)


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
            ]
    def parseArgs(self, uri):
        execfile(RESOURCE('../config.py'), self)
        self['uri'] = uri

    def postOptions(self):
        self.update(self.parent)

        # connect and pull all the events from google calendar
        client = CalendarService()
        print self.updateEvent(client)

    def updateEvent(self, client):
        client.password = self['gventPassword']
        client.email = self['gventEmail']
        client.source = 'TheSoftWorld-Afloat-0.0'
        client.ProgrammaticLogin()

        ev = getExactEvent(client, self['uri'])

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
            import pdb; pdb.set_trace()
            # TODO - change event.when
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
