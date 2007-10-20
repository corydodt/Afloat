#!/usr/bin/python
import time, os, httplib, urllib2
import sys
from getpass import getpass

from twisted.python import usage

join = str.join

sites = {
		"Educational Employees C U": {
            "caps": [ "SIGNON", "BASTMT" ],
			"fid": "321172594",     # ^- this is what i added, for checking/savings/debit accounts- think "bank statement"
			"fiorg": "Educational Employees C U",
			"url": "https://www.eecuonline.org/scripts/isaofx.dll",
			"bankid": "321172594", # bank routing #
		}	
   }

shortSites = { 'eecu': 'Educational Employees C U'
        }
												
def _field(tag,value):
    return "<"+tag+">"+value

def _tag(tag,*contents):
    return join("\r\n",["<"+tag+">"]+list(contents)+["</"+tag+">"])

def _date():
    return time.strftime("%Y%m%d%H%M%S",time.localtime())

def _genuuid():
    return os.popen("uuidgen").read().rstrip().upper()

class OFXClient:
    """Encapsulate an ofx client, config is a dict containg configuration"""
    def __init__(self, config, user, password):
        self.password = password
        self.user = user
        self.config = config
        self.cookie = 3
        config["user"] = user
        config["password"] = password
        if not config.has_key("appid"):
            config["appid"] = "QWIN"  # i've had to fake Quicken to actually get my unwilling test server to talk to me
            config["appver"] = "1200"

    def _cookie(self):
        self.cookie += 1
        return str(self.cookie)

    """Generate signon message"""
    def _signOn(self):
        config = self.config
        fidata = [ _field("ORG",config["fiorg"]) ]
        if config.has_key("fid"):
            fidata += [ _field("FID",config["fid"]) ]
        return _tag("SIGNONMSGSRQV1",
                    _tag("SONRQ",
                         _field("DTCLIENT",_date()),
                         _field("USERID",config["user"]),
                         _field("USERPASS",config["password"]),
                         _field("LANGUAGE","ENG"),
                         _tag("FI", *fidata),
                         _field("APPID",config["appid"]),
                         _field("APPVER",config["appver"]),
                         ))

    def _acctreq(self, dtstart):
        req = _tag("ACCTINFORQ",_field("DTACCTUP",dtstart))
        return self._message("SIGNUP","ACCTINFO",req)

# this is from _ccreq below and reading page 176 of the latest OFX doc.
    def _bareq(self, acctid, dtstart, accttype):
    	config=self.config
        req = _tag("STMTRQ",
               _tag("BANKACCTFROM",
                _field("BANKID", config["bankid"]),
                    _field("ACCTID",acctid),
                _field("ACCTTYPE",accttype)),
               _tag("INCTRAN",
                _field("DTSTART",dtstart),
                _field("INCLUDE","Y")))
        return self._message("BANK","STMT",req)
        
    def _ccreq(self, acctid, dtstart):
        config=self.config
        req = _tag("CCSTMTRQ",
                   _tag("CCACCTFROM",_field("ACCTID",acctid)),
                   _tag("INCTRAN",
                        _field("DTSTART",dtstart),
                        _field("INCLUDE","Y")))
        return self._message("CREDITCARD","CCSTMT",req)

    def _invstreq(self, brokerid, acctid, dtstart):
        dtnow = time.strftime("%Y%m%d%H%M%S",time.localtime())
        req = _tag("INVSTMTRQ",
                   _tag("INVACCTFROM",
                      _field("BROKERID", brokerid),
                      _field("ACCTID",acctid)),
                   _tag("INCTRAN",
                        _field("DTSTART",dtstart),
                        _field("INCLUDE","Y")),
                   _field("INCOO","Y"),
                   _tag("INCPOS",
                        _field("DTASOF", dtnow),
                        _field("INCLUDE","Y")),
                   _field("INCBAL","Y"))
        return self._message("INVSTMT","INVSTMT",req)

    def _message(self,msgType,trnType,request):
        config = self.config
        return _tag(msgType+"MSGSRQV1",
                    _tag(trnType+"TRNRQ",
                         _field("TRNUID",_genuuid()),
                         _field("CLTCOOKIE",self._cookie()),
                         request))
    
    def _header(self):
        return join("\r\n",[ "OFXHEADER:100",
                           "DATA:OFXSGML",
                           "VERSION:102",
                           "SECURITY:NONE",
                           "ENCODING:USASCII",
                           "CHARSET:1252",
                           "COMPRESSION:NONE",
                           "OLDFILEUID:NONE",
                           "NEWFILEUID:"+_genuuid(),
                           ""])

    def baQuery(self, acctid, dtstart, accttype):
    	"""Bank account statement request"""
        return join("\r\n",[self._header(),
 	                  _tag("OFX",
                                self._signOn(),
                                self._bareq(acctid, dtstart, accttype))])
						
    def ccQuery(self, acctid, dtstart):
        """CC Statement request"""
        return join("\r\n",[self._header(),
                          _tag("OFX",
                               self._signOn(),
                               self._ccreq(acctid, dtstart))])

    def acctQuery(self,dtstart):
        return join("\r\n",[self._header(),
                          _tag("OFX",
                               self._signOn(),
                               self._acctreq(dtstart))])

    def invstQuery(self, brokerid, acctid, dtstart):
        return join("\r\n",[self._header(),
                          _tag("OFX",
                               self._signOn(),
                               self._invstreq(brokerid, acctid,dtstart))])

    def doQuery(self,query,name):
        # N.B. urllib doesn't honor user Content-type, use urllib2
        request = urllib2.Request(self.config["url"],
                                  query,
                                  { "Content-type": "application/x-ofx",
                                    "Accept": "*/*, application/x-ofx"
                                  })
        if 1:
            f = urllib2.urlopen(request)
            response = f.read()
            f.close()
            
            f = file(name,"w")
            f.write(response)
            f.close()
	else:
            print request
            print self.config["url"], query
        
        # ...


class Options(usage.Options):
    synopsis = """get site user [account] [CHECKING/SAVINGS/.. if using BASTMT]
  or
get --listSites
___
"""
    optFlags = [['listSites', 'l', 'List all available bank sites']]
    optParameters = [['out', 'o', 'Output filename']]

    def parseArgs(self, siteName=None, user=None, account=None, accountType=None):
        if self['listSites']:
            return

        # manually check that siteName and user were supplied, so we can have
        # the special listSites behavior without causing a UsageError.
        if None in (siteName, user):
            raise usage.UsageError("Wrong number of arguments")

        self['siteName'] = siteName
        if siteName in sites:
            self['site'] = sites[siteName]
        elif siteName in shortSites:
            self['site'] = sites[shortSites[siteName]]
        else:
            raise usage.UsageError("** That is not a site I know. Try --listSites")

        self['user'] = user
        self['account'] = account
        self['accountType'] = accountType

    def opt_listSites(self):
        print "AVAILABLE SITES:\n", join("\n", ('\t'.join(i) for i in shortSites.items()))
        self['listSites'] = True

    def postOptions(self):
        if self['listSites']:
            return

        site = self['site']
        siteName = self['siteName']
        account = self['account']
        dtnow = time.strftime("%Y%m%d", time.localtime())

        dtstart = time.strftime("%Y%m%d", time.localtime(time.time()-31*86400))
        self['outFilename'] = outFilename = fileNamer(siteName, dtnow)

        passwd = getpass(prompt="Bank Password for %s: " % (self['user'],))
        client = OFXClient(site, self['user'], passwd)
        if account is None:
            query = client.acctQuery("19700101000000")
            client.doQuery(query, siteName + "_acct.ofx") 
        else:
            if "CCSTMT" in site["caps"]:
                 query = client.ccQuery(account, dtstart)
            elif "INVSTMT" in site["caps"]:
                 query = client.invstQuery(site["fiorg"], account, dtstart)
            elif "BASTMT" in site["caps"]:
                 query = client.baQuery(account, dtstart, self['accountType'])
            client.doQuery(query, outFilename)

def fileNamer(siteName, date):
    return siteName + date + '.ofx'

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

def optionsRun(argv=None):
    """
    Run the command, and return the options instead
    """
    if argv is None:
        argv = sys.argv
    o = Options()
    try:
        o.parseOptions(argv[1:])
    except usage.UsageError, e:
        print str(o)
        print str(e)
        return o

    return o

if __name__ == '__main__': sys.exit(run())

