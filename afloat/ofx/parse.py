# vi:ft=python
import sys

from twisted.python import usage

import sgmllib

class OFXParser(sgmllib.SGMLParser):
    def __init__(self, *a, **kw):
        sgmllib.SGMLParser.__init__(self, *a, **kw)
        self.data = []
        self.stateStack = []

    def handle_data(self, data):
        pass

    def start_ofx(self, attributes):
        self.start('ofx')

    def start_signonmsgsrsv1(self, attributes):
        self.start('signonmsgsrsv1')

    def start_signupmsgsrsv1(self, attributes):
        self.start('signupmsgsrsv1')

    def start_bankmsgsrsv1(self, attributes):
        self.start('bankmsgsrsv1')

    def end_ofx(self, ):
        self.end('ofx')

    def end_signonmsgsrsv1(self, ):
        self.end('signonmsgsrsv1')

    def end_signupmsgsrsv1(self, ):
        self.end('signupmsgsrsv1')

    def end_bankmsgsrsv1(self, ):
        self.end('bankmsgsrsv1')

    def start(self, tag):
        self.stateStack.append(tag)
        print '  ' * len(self.stateStack), tag

    def end(self, tagName):
        last = ''
        ss = self.stateStack[:]
        while last != tagName and len(ss):
            last = ss.pop(-1)

        if last != tagName:
            raise sgmllib.SGMLParseError(tagName + " ended before it began!")

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
