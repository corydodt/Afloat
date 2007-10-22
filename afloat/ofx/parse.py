# vi:ft=python
import sys

from twisted.python import usage

import sgmllib


class OFXParser(sgmllib.SGMLParser):
    """
    Get financials out.  We need (from signon, acctlist, bankstmt):
       /ofx/signonmsgsrsv1/dtserver
                          /fi/fid (to verify)
                          /users.primacn (to verify)
           /signupmsgsrsv1/acctinfors/acctinfo/bankacctinfo/bankacctfrom/acctid (all available, key)
                                                           /users.bankinfo/ledgerbal/balamt (all by acctid)
                                                                          /availbal/balamt (all by acctid)
                                                                          /hold/dtapplied (all by acctid, key)
                                                                          /hold/desc  (all by acctid by dtapplied)
                                                                          /hold/amt  (all by acctid by dtapplied)
                                                                          /regdcnt (all by accountid)
                                                                          /regdmax (all by accountid)
           /bankmsgsrsv1/stmtrnsrs/stmtrs/bankacctfrom/acctid (to verify)
                                         /banktranlist/stmttrn/fitid (all available, key)
                                                              /trntype
                                                              /trnamt
                                                              /dtposted
                                                              /dtuser
                                                              /memo
                                                              /checknum
                                                              /users.stmt/trnbal (to verify)
                                         /ledgerbal/balamt (assert against signup ledgerbal)
                                         /availbal/balamt (assert against signup ledgerbal)
    """

    def finish_starttag(self, tag, attrs):
        """
        In my subclass, replace "." with "_" in tagnames
        """
        tag = tag.replace('.', '_')
        return sgmllib.SGMLParser.finish_starttag(self, tag, attrs)


    def __init__(self, *a, **kw):
        sgmllib.SGMLParser.__init__(self, *a, **kw)
        self.data = []
        self.stateStack = []
        accounts = {}
        self.inData = 0

    def handle_data(self, data):
        # all container tags seem to contain no data of their own, and all
        # non-container tags do contain data.  so if i found any data, 
        # that means i just closed the last tag.
        data = data.strip()
        if data and len(self.stateStack) > 0:
            if not self.inData: # we just closed and started a tag
                self.end(self.stateStack[-1])

            self.inData = True
            self.data.append(data)

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

    def start_odpacct(self, attributes):
        self.start("odpacct")

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

    def start_stmtrnsrs(self, attributes):
        self.start("stmtrnsrs")

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
        self.inData = False
        self.stateStack.append(tag)
        print '  ' * (len(self.stateStack)-1), tag

    def end_ofx(self, ):
        self.end('ofx')

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
        self.end('users_bankinfo')

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

    def end(self, tagName):
        # print ''.join(self.data)
        self.data = []

        last = ''
        ss = self.stateStack[:]
        while last != tagName and len(ss):
            last = ss.pop(-1)

        if last != tagName:
            raise sgmllib.SGMLParseError(tagName + " ended before it began!")

        print '  ' * (len(ss)), '/' + last

        self.stateStack[:] = ss[:]


class Options(usage.Options):
    synopsis = "parse ofxfile"
    # optParameters = [[long, short, default, help], ...]

    def parseArgs(self, ofxFile):
        self['ofxFile'] = ofxFile

    def postOptions(self):
        p = OFXParser()

        p.feed(open(self['ofxFile']).read())


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

containers = """
"""
