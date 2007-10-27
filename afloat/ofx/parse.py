# vi:ft=python
import sys

from twisted.python import usage

import sgmllib


class Banking(object):
    """
    Your set of accounts, and the server date of the calls we made
    """
    def __init__(self):
        self.accounts = {}

    def addAccount(self, account):
        self.accounts[account.id] = account

    def getAccount(self, id):
        return self.accounts[id]


class Account(object):
    """
    A single account, with all your transactions
    """
    def __init__(self):
        self.transactions = {}

    def addTransaction(self, txn):
        self.transactions[txn.id] = txn


class Transaction(object):
    """
    One transaction (date, memo, checknum, amount)
    """
    def __init__(self):
        pass


class OFXParser(sgmllib.SGMLParser):
    """
    Get financials out.  We need (from signon, acctlist, bankstmt):
X      /ofx/signonmsgsrsv1/dtserver
X                         /fi/fid (to verify)
X                         /users.primacn (to verify)
X          /signupmsgsrsv1/acctinfors/acctinfo/bankacctinfo/bankacctfrom/acctid (all available, key)
_                                                          /users.bankinfo/ledgerbal/balamt (all by acctid)
_                                                                         /availbal/balamt (all by acctid)
_                                                                         /hold/dtapplied (all by acctid, key)
_                                                                              /desc  (all by acctid by dtapplied)
_                                                                              /amt  (all by acctid by dtapplied)
_                                                                         /regdcnt (all by accountid)
_                                                                         /regdmax (all by accountid)
X          /bankmsgsrsv1/stmtrnsrs/stmtrs/bankacctfrom/acctid (to verify)
X                                        /banktranlist/stmttrn/fitid (all available, key)
_                                                             /trntype
_                                                             /trnamt
_                                                             /dtposted
_                                                             /dtuser
_                                                             /memo
_                                                             /checknum
_                                                             /users.stmt/trnbal (to verify)
_                                        /ledgerbal/balamt (assert against signup ledgerbal)
_                                        /availbal/balamt (assert against signup ledgerbal)
    """

    def finish_starttag(self, tag, attrs):
        """
        In my subclass, replace "." with "_" in tagnames
        """
        tag = tag.replace('.', '_')
        return sgmllib.SGMLParser.finish_starttag(self, tag, attrs)

    def finish_endtag(self, tag, ):
        """
        In my subclass, replace "." with "_" in tagnames
        """
        tag = tag.replace('.', '_')
        return sgmllib.SGMLParser.finish_endtag(self, tag, )

    def __init__(self, *a, **kw):
        sgmllib.SGMLParser.__init__(self, *a, **kw)
        self._data = []
        self._stateStack = []
        self.banking = Banking()
        self.inData = 0
        self.currentAccount = None
        self.currentTransaction = None

    def handle_data(self, data):
        data = data.strip()
        if data:
            self.inData = True
            self._data.append(data)

    def start_sonrs(self, attributes):
        self.start("sonrs")

    def start_language(self, attributes):
        self.start("language")

    def start_dtprofup(self, attributes):
        self.start("dtprofup")

    def start_dtacctup(self, attributes):
        self.start("dtacctup")

    def start_fi(self, attributes):
        self.start("fi")

    def start_org(self, attributes):
        self.start("org")

    def start_fid(self, attributes):
        self.start("fid")

    def start_users_type(self, attributes):
        self.start("users.type")

    def start_intu_bid(self, attributes):
        self.start("intu.bid")

    def start_intu_userid(self, attributes):
        self.start("intu.userid")

    def start_users_dtlastlogin(self, attributes):
        self.start("users.dtlastlogin")

    def start_acctinfotrnsrs(self, attributes):
        self.start("acctinfotrnsrs")

    def start_trnuid(self, attributes):
        self.start("trnuid")

    def start_status(self, attributes):
        self.start("status")

    def start_code(self, attributes):
        self.start("code")

    def start_severity(self, attributes):
        self.start("severity")

    def start_message(self, attributes):
        self.start("message")

    def start_cltcookie(self, attributes):
        self.start("cltcookie")

    def start_acctinfors(self, attributes):
        self.start("acctinfors")

    def start_acctinfo(self, attributes):
        self.start("acctinfo")

    def start_phone(self, attributes):
        self.start("phone")

    def start_users_acctnickname(self, attributes):
        self.start("users.acctnickname")

    def start_users_stmtdesc(self, attributes):
        self.start("users.stmtdesc")

    def start_bankacctinfo(self, attributes):
        self.start("bankacctinfo")

    def start_bankacctfrom(self, attributes):
        self.start("bankacctfrom")

    def start_bankid(self, attributes):
        self.start("bankid")

    def start_accttype(self, attributes):
        self.start("accttype")

    def start_suptxdl(self, attributes):
        self.start("suptxdl")

    def start_xfersrc(self, attributes):
        self.start("xfersrc")

    def start_xferdest(self, attributes):
        self.start("xferdest")

    def start_svcstatus(self, attributes):
        self.start("svcstatus")

    def start_users_bankinfo(self, attributes):
        self.start("users.bankinfo")

    def start_ledgerbal(self, attributes):
        self.start("ledgerbal")

    def start_dtasof(self, attributes):
        self.start("dtasof")

    def start_availbal(self, attributes):
        self.start("availbal")

    def start_label(self, attributes):
        self.start("label")

    def start_shareclass(self, attributes):
        self.start("shareclass")

    def start_sdacn(self, attributes):
        self.start("sdacn")

    def start_micr(self, attributes):
        self.start("micr")

    def start_dthistavail(self, attributes):
        self.start("dthistavail")

    def start_odpact(self, attributes):
        self.start("odpact")

    def start_iraflg(self, attributes):
        self.start("iraflg")

    def start_hold(self, attributes):
        self.start("hold")

    def start_type(self, attributes):
        self.start("type")

    def start_subtype(self, attributes):
        self.start("subtype")

    def start_dtreleased(self, attributes):
        self.start("dtreleased")

    def start_regd(self, attributes):
        self.start("regd")

    def start_edpdeposit(self, attributes):
        self.start("edpdeposit")

    def start_cpaylimit(self, attributes):
        self.start("cpaylimit")

    def start_users_businessdate(self, attributes):
        self.start("users.businessdate")

    def start_stmttrnrs(self, attributes):
        self.start("stmttrnrs")

    def start_stmtrs(self, attributes):
        self.start("stmtrs")

    def start_curdef(self, attributes):
        self.start("curdef")

    def start_banktranlist(self, attributes):
        self.start("banktranlist")

    def start_dtstart(self, attributes):
        self.start("dtstart")

    def start_dtend(self, attributes):
        self.start("dtend")

    def start_stmttrn(self, attributes):
        self.start("stmttrn")

    def start_name(self, attributes):
        self.start("name")

    def start_users_stmt(self, attributes):
        self.start("users.stmt")

    def start_tracenumber(self, attributes):
        self.start("tracenumber")

    def start_hyperlink(self, attributes):
        self.start("hyperlink")

    def start_ofx(self, attributes):
        self.start('ofx')

    def start_signonmsgsrsv1(self, attributes):
        self.start('signonmsgsrsv1')

    def start_signupmsgsrsv1(self, attributes):
        self.start('signupmsgsrsv1')

    def start_bankmsgsrsv1(self, attributes):
        self.start('bankmsgsrsv1')

    def start_dtserver(self, attributes):
        self.start('dtserver')

    def start_users_primacn(self, attributes): # argh
        self.start('users.primacn')

    def start_acctid(self, attributes):
        self.start("acctid")

    def start_balamt(self, attributes):
        self.start("balamt")

    def start_dtapplied(self, attributes):
        self.start("dtapplied")

    def start_desc(self, attributes):
        self.start("desc")

    def start_amt(self, attributes):
        self.start("amt")

    def start_regdcnt(self, attributes):
        self.start("regdcnt")

    def start_regdmax(self, attributes):
        self.start("regdmax")

    def start_fitid(self, attributes):
        self.start("fitid")

    def start_trntype(self, attributes):
        self.start("trntype")

    def start_trnamt(self, attributes):
        self.start("trnamt")

    def start_dtposted(self, attributes):
        self.start("dtposted")

    def start_dtuser(self, attributes):
        self.start("dtuser")

    def start_memo(self, attributes):
        self.start("memo")

    def start_checknum(self, attributes):
        self.start("checknum")

    def start_trnbal(self, attributes):
        self.start("trnbal")

    def start(self, tag):
        # this is somewhat fishy.  "inData" means the last thing we saw was
        # data.  If we've just seen data, then the last tag was NOT A
        # CONTAINER, because OFX doesn't have any data tags that are also
        # containers.  If the last tag was NOT A CONTAINER, it should close
        # now. 
        if self.inData and self._stateStack:
            self.end(self._stateStack[-1])
        self.inData = False
        self._stateStack.append(tag)
        print '  ' * (len(self._stateStack)-1), tag

    def end_ofx(self, ):
        self.end('ofx')
        for account in self.banking.accounts.values():
            print 'account #', account.id
            for txn in account.transactions.values():
                print 'transaction #', txn.id

    def end_signonmsgsrsv1(self, ):
        self.end('signonmsgsrsv1')

    def end_signupmsgsrsv1(self, ):
        self.end('signupmsgsrsv1')

    def end_bankmsgsrsv1(self, ):
        self.end('bankmsgsrsv1')

    def end_sonrs(self, ):
        self.end('sonrs')

    def end_fi(self, ):
        self.end('fi')

    def end_acctinfotrnsrs(self, ):
        self.end('acctinfotrnsrs')

    def end_status(self, ):
        self.end('status')

    def end_acctinfors(self, ):
        self.end('acctinfors')

    def end_acctinfo(self, ):
        self.end('acctinfo')

    def end_bankacctinfo(self, ):
        self.end('bankacctinfo')

    def end_bankacctfrom(self, ):
        self.end('bankacctfrom')

    def end_users_bankinfo(self, ):
        self.end('users.bankinfo')

    def end_odpacct(self, ):
        self.end('odpacct')

    def end_hold(self, ):
        self.end('hold')

    def end_stmtrnsrs(self, ):
        self.end('stmtrnsrs')

    def end_stmtrs(self, ):
        self.end('stmtrs')

    def end_banktranlist(self, ):
        self.end('banktranlist')

    def end_stmttrn(self, ):
        self.end('stmttrn')

    def end_users_stmt(self, ):
        self.end('users.stmt')

    def end_ledgerbal(self, ):
        self.end('ledgerbal')

    def end_availbal(self, ):
        self.end('availbal')

    def dataUnknown(self, tagName, data, stack):
        pass 
        # print tagName, data

    def data_fid(self, tagName, data, stack):
        print 'server bank fid: %s' % (data,)
        self.banking.fid = data

    def data_dtserver(self, tagName, data, stack):
        print 'server date: %s' % (data,)
        self.banking.dtserver = data

    def data_users_primacn(self, tagName, data, stack):
        print 'users.primacn: %s' % (data,)
        self.banking.primaryAccount = data

    def data_message(self, tagName, data, stack):
        assert 0, "message should have some data in it"
        print 'message: ', data

    def data_fitid(self, tagName, data, stack):
        txn  = Transaction()
        txn.id = data
        ## self.currentAccount.addTransaction(txn)

    def data_acctid(self, tagName, data, stack):
        if stack[-6:] == ['signupmsgsrsv1', 'acctinfotrnrs', 'acctinfors',
                'acctinfo', 'bankacctinfo', 'bankacctfrom', 'acctid']:
            account = Account()
            account.id = data
            self.banking.addAccount(account)
            return
        if stack[-4:] == ['bankmsgsrsv1', 'stmttrnrs', 'stmtrs',
                'bankacctfrom', 'acctid']:
            self.currentAccount = self.banking.getAccount(data)
            return

    def end(self, tagName):
        # clean up the tag stack first, closing inner tags depth-first
        last = ''
        ss = self._stateStack[::-1]
        for n, stackTag in enumerate(ss):
            if stackTag != tagName:
                getattr(self, 'end_%s' % (stackTag,), lambda:None)()
                self.end(last)
            else:
                break

        if stackTag != tagName:
            raise sgmllib.SGMLParseError(tagName + " ended before it began!")

        self.finalizeTagData(
        
        print '  ' * (len(ss)), '/' + tagName

        self._stateStack[:] = list(reversed(ss[n:]))

    def finalizeTagData(self, tagName):
        self.inData = False

        tnUnderscores = tagName.replace('.', '_')
        dataHandler = getattr(self, 'data_%s' % (tnUnderscores,), self.dataUnknown)
        data = ''.join(self._data)
        dataHandler(tnUnderscores, data, self._stateStack[:])

        self._data = []



class Options(usage.Options):
    synopsis = "parse directory"
    # optParameters = [[long, short, default, help], ...]

    def parseArgs(self, directory):
        self['directory'] = directory

    def postOptions(self):
        p = OFXParser()
        d = self['directory']
        for ofx in ['%s/%s.ofx' % (d,x) for x in 'account', 'statement']:
            doc = open(ofx).read()
            p.feed(doc)


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
