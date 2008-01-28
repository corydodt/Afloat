"""
Twistd plugin to run Afloat.

Twisted 2.5 or later is required to use this.
"""

from zope.interface import implements

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker

from afloat.resource import Root, VhostFakeRoot
from afloat.service import AfloatService, STFUSite

class Options(usage.Options):
    optParameters = [['port', 'p', '7780', 'Port to run on'],
                     ['interface', None, '0.0.0.0', 'IP address of an interface to run on.'],
                     ]
    ## optFlags = [['dev', None, 'Enable development features']]


class AfloatServerMaker(object):
    """
    Framework boilerplate class: This is used by twistd to get the service
    class.

    Basically exists to hold the IServiceMaker interface so twistd can find
    the right makeService method to call.
    """
    implements(IServiceMaker, IPlugin)
    tapname = "afloat"
    description = "Afloat predicts your balance online"
    options = Options

    def makeService(self, options):
        """
        Construct the test daemon.
        """
        # do startup tasks, if any.
        root = Root()
        resource = VhostFakeRoot(root)
        factory = STFUSite(resource)
        port = int(options['port'])
        svc = AfloatService(port, factory, interface=options['interface'])
        root.service = svc
        
        return svc


# Now construct an object which *provides* the relevant interfaces

# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMaker.

serviceMaker = AfloatServerMaker()
