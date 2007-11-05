import sys
import re
from getpass import getpass
import datetime

from twisted.python import usage

import atom
from gdata.calendar.service import CalendarEventQuery, CalendarService
from gdata import calendar

CALENDAR_NAMES = {
        'finance': 'bd7j228bhdt527n0o4pk8dhf50@group.calendar.google.com'
}

# afloat#paid ; value: a datetime that indicates when it was paid
EVENT_PAID = 'http://thesoftworld.com/2007/afloat#paid'
# afloat#bankId ; value: a string that matches a bank trnid
EVENT_BANKID = 'http://thesoftworld.com/2007/afloat#bankId'
# afloat#originalDate ; value: a datetime that indicates the user-entered date
EVENT_ORIGINALDATE = 'http://thesoftworld.com/2007/afloat#originalDate'
# afloat#amount ; value: an integer (cents.. divide by 100 for dollars)
EVENT_AMOUNT = 'http://thesoftworld.com/2007/afloat#amount'
# afloat#fromAccount ; value: string account number
EVENT_FROMACCOUNT = 'http://thesoftworld.com/2007/afloat#fromAccount'
# afloat#toAccount ; value: string account number
EVENT_TOACCOUNT = 'http://thesoftworld.com/2007/afloat#toAccount'


class NoAmountError(Exception):
    pass


class MissingToAccount(Exception):
    """
    An event that needed a To account didn't have one.  Events without any to
    or from are defaulted to checking; this gets raised ONLY if an event with
    a From account doesn't have a To account.
    """

def getExactEvent(client, uri):
    return client.GetCalendarEventEntry(uri)

def retitleEvent(client, event, new_title):
    """Updates the title of the specified event with the specified new_title.
    Note that the UpdateEvent method (like InsertEvent) returns the
    CalendarEventEntry object based upon the data returned from the server
    after the event is inserted.  This represents the 'official' state of
    the event on the server.  The 'edit' link returned in this event can
    be used for future updates.  Due to the use of the 'optimistic concurrency'
    method of version control, most GData services do not allow you to send
    multiple update requests using the same edit URL.  Please see the docs:
    http://code.google.com/apis/gdata/reference.html#Optimistic-concurrency
    """

    previous_title = event.title.text
    event.title.text = new_title
    print 'Updating title of event from:\'%s\' to:\'%s\'' % (
        previous_title, event.title.text,)
    return client.UpdateEvent(event.GetEditLink().href, event)

def addExtendedProperty(client, event, name, value):
    """
    Adds an arbitrary name/value pair to the event.  This value is only
    exposed through the API.  Extended properties can be used to store extra
    information needed by your application.  The recommended format is used as
    the default arguments above.  The use of the URL format is to specify a
    namespace prefix to avoid collisions between different applications.
    """
    event.extended_property.append(
        calendar.ExtendedProperty(name=name, value=value))
    print 'Adding extended property to event: \'%s\'=\'%s\'' % (name, value,)
    return client.UpdateEvent(event.GetEditLink().href, event)

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

dollarRx = re.compile(r'^\$[0-9]+(\.[0-9]+)?$')
noDollarRx = re.compile(r'^[0-9]+(\.[0-9]+)?$')

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

def fixupEvent(client, event):
    """
    Parse numerics in event's title and set extended amount attribute on
    event.  Parse from/to fields from event description and get From/To for a
    transaction.
    Do nothing if event already has these attributes.
    """
    changed = 0
    propsFound = [x.name for x in event.extended_property]
    if EVENT_AMOUNT not in propsFound:
        amount = findAmount(event.title.text)
        if amount is None:
            raise NoAmountError(event)
        prop = calendar.ExtendedProperty(name=EVENT_AMOUNT, value=str(amount))
        event.extended_property.append(prop)
        changed = 1
    if EVENT_TOACCOUNT not in propsFound and event.content.text:
        fromAccount, toAccount = findAccounts(event.content.text)
        if toAccount is not None:
            prop = calendar.ExtendedProperty(name=EVENT_TOACCOUNT,
                    value=toAccount)
            event.extended_property.append(prop)
            changed = 1
        if fromAccount is not None:
            if toAccount is None:
                raise MissingToAccount(event)
            prop = calendar.ExtendedProperty(name=EVENT_FROMACCOUNT,
                    value=fromAccount)
            event.extended_property.append(prop)
    if EVENT_ORIGINALDATE not in propsFound:
        prop = calendar.ExtendedProperty(name=EVENT_ORIGINALDATE,
                value=event.when[0].start_time)
        event.extended_property.append(prop)

    if changed:
        client.UpdateEvent(event.GetEditLink().href, event)


def dateQuery(client, calendarName, start_date, end_date):
    """
    Retrieves events from the server which occur during the specified date
    range.
    """
    query = CalendarEventQuery(calendarName, 'private', 'full')
    query.start_min = start_date
    query.start_max = end_date
    return client.CalendarQuery(query)


class CalendarEventString(object):
    """
    A marshallable, trivially parseable form of a calendar event
    """
    def __init__(self, href, title, paidDate, bankId, originalDate,
            expectedDate, amount, fromAccount, toAccount, ):
        coalesce = lambda x: (None if not x else unicode(x))
        self.href = unicode(href)
        self.title = unicode(title)
        self.paidDate = parseDateYMD(paidDate)
        self.bankId = coalesce(bankId)
        self.originalDate = parseDateYMD(originalDate)
        self.expectedDate = parseDateYMD(expectedDate)
        self.amount = int(amount)
        self.fromAccount = coalesce(fromAccount)
        self.toAccount = coalesce(toAccount)

    def __str__(self):
        ret = "%s %s %s %s %s %s %s %s %s" % (
            self.href,
            re.sub('\s+', '+', self.title),
            formatDateYMD(self.paidDate) or '~',
            self.bankId or '~',
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
        assert len(splits) == 9
        parseTilde = lambda x: (None if x == '~' else x)
        new1 = cls( splits[0],
                ' '.join(splits[1].split('+')),
                parseTilde(splits[2]),
                parseTilde(splits[3]),
                splits[4],
                splits[5],
                splits[6],
                parseTilde(splits[7]),
                parseTilde(splits[8]),
                )
        return new1


class GetEvents(usage.Options):
    """
    Print the events as a list of them, fields separated by spaces
    """
    synopsis = 'date1 date2'
    optFlags = [['fixup', 'f', 'Do the fixup step, adding metadata to '
        'calendar items that do not have it'],
    ]
    def parseArgs(self, date1, date2):
        self['dateStart'] = date1
        self['dateEnd'] = date2

    def postOptions(self):
        self.update(self.parent)

        d1 = self['dateStart']
        d2 = self['dateEnd']

        client = CalendarService()
        client.password = self['password']
        client.email = self['email']
        client.source = 'TheSoftWorld-Afloat-0.0'
        client.ProgrammaticLogin()

        feed = dateQuery(client, self['calendarName'], d1, d2)

        for e in feed.entry:
            if self['fixup']:
                try:
                    fixupEvent(client, e)
                except NoAmountError:
                    pass

            eProps = {}
            for prop in e.extended_property:
                eProps[prop.name] = prop.value
            get = lambda k: eProps.get(k)
            href = e.GetSelfLink().href

            # skip over special events created when you break a recurring
            # event  (??)
            if e.original_event is not None:
                continue

            for when in e.when:
                print CalendarEventString(href,
                        e.title.text,
                        get(EVENT_PAID),
                        get(EVENT_BANKID),
                        get(EVENT_ORIGINALDATE),
                        when.start_time,
                        get(EVENT_AMOUNT),
                        get(EVENT_FROMACCOUNT),
                        get(EVENT_TOACCOUNT),
                        )


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


class Options(usage.Options):
    synopsis = "readcal --connect=calendar//email[//password] <subcommand>"
    subCommands = [
        ['get-events', None, GetEvents, 'Get all events in given date range'],
        ## ['add-event', 'add', AddEvent, 'Add an event'],
        ## ['remove-event', 'rm', RemoveEvent, 'Remove an event - TODO - break recurrence if necessary'],
        ## ['update-event', 'update', UpdateEvent, 'Update an event - TODO - break recurrence if necessary'],
    ]
    optParameters = [
        ## see opt_connect
    ]

    def opt_connect(self, connectString):
        splits = re.split('//', connectString, 2)
        if len(splits) < 2:
            raise usage.UsageError("** Invalid connect string")

        calendar = splits.pop(0)
        self['calendarName'] = CALENDAR_NAMES.get(calendar, calendar)
        email = self['email'] = splits.pop(0)
        if splits:
            self['password'] = splits.pop(0)
        else:
            self['password'] = getpass(prompt="Password (%s): " % (email,))

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
