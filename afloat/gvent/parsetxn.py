"""
A simpleparse parser for the "title" of a scheduled transaction.
Extracts the amount, comments, etc.
"""
from itertools import chain, repeat
import re

from simpleparse import parser, dispatchprocessor as disp
from simpleparse.common import numbers
## appease pyflakes:
numbers


class NoAmountError(Exception):
    pass


grammar = ( # {{{
r'''
<l> :=               letter
<n> :=               int
<d> :=               digit
<wsc> :=             [ \t]
<ws> :=              wsc*
<cPunct> :=          [-+.,<>';:"{}\\/|`~!@#$%^&*()_=]
<c> :=               (l/d/cPunct)
word :=              c+
<sign> :=            [-+]
<comma_number> :=    (d/','/'.')+
comment :=           '[', ws, (word, ws)*, ']'
amount :=            '$'?, sign?, comma_number
check :=             '#', n
>thing< :=           comment/amount/check/word
txnExpression :=     ws, (thing, ws)*
txnExpressionRoot := txnExpression
''') # }}}


TOKEN_STUFF = 'TOKEN_STUFF'
TOKEN_AMOUNT = 'TOKEN_AMOUNT'
TOKEN_DOLLAR = 'TOKEN_DOLLAR'
TOKEN_COMMENT = 'TOKEN_COMMENT'
TOKEN_CHECK_NUMBER = 'TOKEN_CHECK_NUMBER'
EXCEPTION_RAISED = 'EXCEPTION_RAISED'


alnumRx = re.compile('[_\W\s]+', flags=re.U)


def splitWords(s):
    """Return all the words after normalizing case and punctuation and spaces"""
    s = s.lower()
    return alnumRx.sub(' ', s).split()


class TxnTitle(object):
    @classmethod
    def fromString(cls, st):
        txnParser = parser.Parser(grammar, root="txnExpressionRoot")
        p = Processor()
        suc, _, __ = txnParser.parse(st, processor=p)
        assert suc
        title = cls()
        title.amount = p.amount
        title.checkNumber = p.checkNumber
        title.stuff = " ".join([x[1] for x in p.current if x[0] is TOKEN_STUFF])
        return title

    def keywords(self):
        """Return all the keywords (no comments, check numbers or amounts)"""
        return splitWords(self.stuff)


class Processor(disp.DispatchProcessor):
    def __init__(self, *a, **kw):
        #  disp.DispatchProcessor.__init__(self, *a, **kw) -- no
        self.current = []
        self.checkNumber = None
        self.dollarAmount = None

    def fixAmount(self):
        """
        There can be only one amount.  Prefer amounts with dollar signs.
        Also check that there's at least one amount.
        """
        amounts = []

        _waitingForDollarAmount = None
        for n, (type, tok) in enumerate(self.current):
            if type is TOKEN_DOLLAR:
                _waitingForDollarAmount = True
                continue
            elif type is TOKEN_AMOUNT:
                if _waitingForDollarAmount:
                    self.dollarAmount = tok
                    break
                else:
                    amounts.append(tok)
            _waitingForDollarAmount = False

        if not self.dollarAmount:
            if amounts == []:
                raise NoAmountError()
            else:
                self.dollarAmount = amounts[0]

    def txnExpression(self, (t, s1, s2, sub), buffer):
        r = disp.dispatchList(self, sub, buffer)
        self.fixAmount()
        return r

    def amount(self, (t, s1, s2, sub), buffer):
        st = buffer[s1:s2].replace(',', '')
        if st[0] == '$':
            self.current.append((TOKEN_DOLLAR, '$'))
            st = st[1:]
        a = int(float(st)*100)
        self.current.append((TOKEN_AMOUNT, a))

    def word(self, (t, s1, s2, sub), buffer):
        st = buffer[s1:s2]
        if len(self.current) > 0 and self.current[-1][0] is TOKEN_STUFF:
            last = self.current[-1][1] + " " + st
            self.current[-1] = (TOKEN_STUFF, last)
        else:
            self.current.append((TOKEN_STUFF, st))

    def comment(self, (t, s1, s2, sub), buffer):
        st = buffer[s1+1:s2-1]
        self.current.append((TOKEN_COMMENT, st))

    def check(self, (t, s1, s2, sub), buffer):
        if self.checkNumber is None:
            st = buffer[s1+1:s2]
            cn = int(st)
            self.current.append((TOKEN_CHECK_NUMBER, cn))
            self.checkNumber = cn
        else:
            st = buffer[s1:s2]
            self.current.append((TOKEN_STUFF, st))


# save typing for tests.. {{{
T_AMOUNT1 = (TOKEN_AMOUNT, 9900)
T_AMOUNT2 = (TOKEN_AMOUNT, -9900)
T_AMOUNT3 = (TOKEN_AMOUNT, 9922)
T_AMOUNT4 = (TOKEN_AMOUNT, -9922)
T_AMOUNT5 = (TOKEN_AMOUNT, 1100)
T_CHECK = (TOKEN_CHECK_NUMBER, 23)
T_DOLLAR = (TOKEN_DOLLAR, '$')
VERIFY_AMOUNT = 'VERIFY_AMOUNT'
VERIFY_CHECK = 'VERIFY_CHECK'
T_VERIFY_CHECK = (VERIFY_CHECK, 23)
T_VERIFY_AMOUNT1 = (VERIFY_AMOUNT, 9900)
T_VERIFY_AMOUNT2 = (VERIFY_AMOUNT, -9900)
T_VERIFY_AMOUNT3 = (VERIFY_AMOUNT, 9922)
T_VERIFY_AMOUNT4 = (VERIFY_AMOUNT, -9922)

tests = ( #
# amounts, negative, positive, with or without float, with or without $,
# various positions
('$99 foo bar',       [T_DOLLAR, T_AMOUNT1, (TOKEN_STUFF, "foo bar"),
    T_VERIFY_AMOUNT1]),
('$-99 foo bar',      [T_DOLLAR, T_AMOUNT2, (TOKEN_STUFF, "foo bar"),
    T_VERIFY_AMOUNT2]),
('$99.22 foo bar',    [T_DOLLAR, T_AMOUNT3, (TOKEN_STUFF, "foo bar"),
    T_VERIFY_AMOUNT3]),
('$-99.22 foo bar',   [T_DOLLAR, T_AMOUNT4, (TOKEN_STUFF, "foo bar")]),
('foo $99 bar',       [(TOKEN_STUFF, 'foo'), T_DOLLAR, T_AMOUNT1,
    (TOKEN_STUFF, "bar"),
    T_VERIFY_AMOUNT1]),
('foo $-99.22 bar',   [(TOKEN_STUFF, 'foo'), T_DOLLAR, T_AMOUNT4,
    (TOKEN_STUFF, "bar"),
    T_VERIFY_AMOUNT4]),
('foo bar $99',       [(TOKEN_STUFF, 'foo bar'), T_DOLLAR, T_AMOUNT1,
    T_VERIFY_AMOUNT1]),
('foo bar $-99.22',   [(TOKEN_STUFF, 'foo bar'), T_DOLLAR, T_AMOUNT4,
    T_VERIFY_AMOUNT4]),
('99 foo bar',        [T_AMOUNT1, (TOKEN_STUFF, "foo bar"),
    T_VERIFY_AMOUNT1]),
('-99 foo bar',       [T_AMOUNT2, (TOKEN_STUFF, "foo bar"),
    T_VERIFY_AMOUNT2]),
('foo -99.22 bar',    [(TOKEN_STUFF, 'foo'), T_AMOUNT4, (TOKEN_STUFF, "bar"),
    T_VERIFY_AMOUNT4]),
('foo bar -99.22',    [(TOKEN_STUFF, 'foo bar'), T_AMOUNT4,
    T_VERIFY_AMOUNT4]),
# comments, various positions
('foo [bar] $-99.22', [(TOKEN_STUFF, 'foo'), (TOKEN_COMMENT, 'bar'), T_DOLLAR,
    T_AMOUNT4,
    T_VERIFY_AMOUNT4]),
('[bar] foo $99',     [(TOKEN_COMMENT, 'bar'), (TOKEN_STUFF, 'foo'), T_DOLLAR,
    T_AMOUNT1,
    T_VERIFY_AMOUNT1]),
('[bar foo] $99',     [(TOKEN_COMMENT, 'bar foo'), T_DOLLAR, T_AMOUNT1,
    T_VERIFY_AMOUNT1]),
('$99 []',            [T_DOLLAR, T_AMOUNT1, (TOKEN_COMMENT, ''),
    T_VERIFY_AMOUNT1]),
('[comment1] foo bar $99 [comment2]', [(TOKEN_COMMENT, 'comment1'),
    (TOKEN_STUFF, 'foo bar'), T_DOLLAR, T_AMOUNT1, (TOKEN_COMMENT,
        'comment2'),
    T_VERIFY_AMOUNT1]),
# checknumbers, various positions
('#23 foo $99',       [T_CHECK, (TOKEN_STUFF, 'foo'), T_DOLLAR, T_AMOUNT1,
    T_VERIFY_AMOUNT1, T_VERIFY_CHECK]),
('foo #23 $99',       [(TOKEN_STUFF, 'foo'), T_CHECK, T_DOLLAR, T_AMOUNT1,
    T_VERIFY_AMOUNT1, T_VERIFY_CHECK]),
('foo $99 #23',       [(TOKEN_STUFF, 'foo'), T_DOLLAR, T_AMOUNT1, T_CHECK,
    T_VERIFY_AMOUNT1, T_VERIFY_CHECK]),
# stray dollar sign
('$ 99 foo',          [(TOKEN_STUFF, '$'), T_AMOUNT1, (TOKEN_STUFF, 'foo'),
    T_VERIFY_AMOUNT1]),
('$ foo 99',          [(TOKEN_STUFF, '$ foo'), T_AMOUNT1,
    T_VERIFY_AMOUNT1]),
# stray pound sign
('# 11 foo $99',      [(TOKEN_STUFF, '#'), T_AMOUNT5, (TOKEN_STUFF, 'foo'),
    T_DOLLAR, T_AMOUNT1, T_VERIFY_AMOUNT1]),
# more than one special class on a line
('foo $99 #23 #11',   [(TOKEN_STUFF, 'foo'), T_DOLLAR, T_AMOUNT1, T_CHECK,
    (TOKEN_STUFF, '#11'), T_VERIFY_AMOUNT1, T_VERIFY_CHECK]),
('foo 99 11',         [(TOKEN_STUFF, 'foo'), T_AMOUNT1, (TOKEN_AMOUNT, 1100),
    T_VERIFY_AMOUNT1]),
('foo 11 $99',        [(TOKEN_STUFF, 'foo'), T_AMOUNT5, T_DOLLAR, T_AMOUNT1,
    T_VERIFY_AMOUNT1]),
('foo $99 $11',       [(TOKEN_STUFF, 'foo'), T_DOLLAR, T_AMOUNT1, T_DOLLAR,
    T_AMOUNT5,
    T_VERIFY_AMOUNT1]),
('foo $-99 $11',      [(TOKEN_STUFF, 'foo'), T_DOLLAR, T_AMOUNT2, T_DOLLAR,
    T_AMOUNT5,
    T_VERIFY_AMOUNT2]),
# exception handling (no amount)
('foo bar',           [(EXCEPTION_RAISED, NoAmountError,)]),
('foo bar [$11]',     [(EXCEPTION_RAISED, NoAmountError,)]),
# misc
('foo $#11 bar 99',   [(TOKEN_STUFF, 'foo $#11 bar'), T_AMOUNT1,
    T_VERIFY_AMOUNT1]),
('foo $#11 bar 9,999',[(TOKEN_STUFF, 'foo $#11 bar'), (TOKEN_AMOUNT, 999900),
    (VERIFY_AMOUNT, 999900)]),
) # }}}


def padSeq(seq, padding):
    return chain(seq, repeat(padding))


def padZip(l1, l2, padding=None):
    """
    Return zip(l1, l2), but the shorter sequence will be padded to the length
    of the longer sequence by the padding
    """
    if len(l1) > len(l2):
        return zip(l1, padSeq(l2, padding))
    elif len(l1) < len(l2):
        return zip(padSeq(l1, padding), l2)

    return zip(l1, l2)


if __name__ == '__main__':
    txnParser = parser.Parser(grammar, root="txnExpressionRoot")
    for test, expected in tests:
        print test
        try:
            p = Processor()
            suc, _ , next = txnParser.parse(test, processor=p)
            assert suc
            result = p.current
        except Exception, e:
            result = [(EXCEPTION_RAISED, e.__class__)]
        for r, e in padZip(result, expected):
            if e[0] is VERIFY_AMOUNT:
                assert e[1] == p.dollarAmount, "%s %s" % (e, p.dollarAmount)
            elif e[0] is VERIFY_CHECK:
                assert e[1] == p.checkNumber, "%s %s" % (e, p.checkNumber)
            else:
                assert e == r, "%s %s" % (e, r)

        # assert result == expected, "%s != %s" % (result, expected)
