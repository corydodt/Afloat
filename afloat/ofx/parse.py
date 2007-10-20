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

    def start_signonmsgsrv1(self, attributes):
        self.start('signonmsgsrv1')

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
            last = self.stateStack.pop(-1)

        if last != tagName:
            raise sgmllib.SGMLParseError(tagName + " ended before it began!")

        self.stateStack[:] = ss[:]


p = OFXParser()

p.feed(open('Educational Employees C U20071018.ofx').read())

containers = """
"""
