from zope.interface import implements
from twisted.internet import reactor, interfaces
from twisted.internet.error import CannotListenError
from twisted.web import server
from resource import CSPRootResource

class CometPort(object):    
    """ A cometsession.Port object can be used in two different ways.
    # Method 1
    reactor.listenWith(cometsession.Port, 9999, SomeFactory())
    
    # Method 2
    root = twisted.web.resource.Resource()
    site = twisted.web.server.Site(root)
    reactor.listenTcp(site, 9999)
    reactor.listenWith(cometsession.Port, factory=SomeFactory(), resource=root, childName='tcp')
    
    Either of these methods should acheive the same effect, but Method2 allows you
    To listen with multiple protocols on the same port by using different urls.
    """
    implements(interfaces.IListeningPort)

    def __init__(self, port=None, factory=None, backlog=50, interface='', reactor=None, resource=None, childName=None, killTimeout=10):
        self.port = port
        self.factory = factory
        self.backlog = backlog
        self.interface = interface
        self.resource = resource
        self.childName = childName
        self.killTimeout = killTimeout
        self.cspTcpPort = None
        self.listening = False

    def startListening(self):
        if not self.listening:
            self.listening = True
            csp = CSPRootResource(self.killTimeout)
            csp.setConnectCb(self.connectionMade)
            if self.port:
                self.cspTcpPort = reactor.listenTCP(self.port, server.Site(csp), self.backlog, self.interface)
            elif self.resource and self.childName:
                self.resource.putChild(self.childName, csp)
        else:
            raise CannotListenError("Already listening...")

    def stopListening():
        if self.cspTcpPort:
            self.listening = False
            self.cspTcpPort.stopListening()
        elif self.resource:
            pass # TODO: self.resource.removeChild(self.childName) ?

    def connectionMade(self, session):
        protocol = self.factory.buildProtocol(session.getPeer())
        if protocol is None: 
            return session.loseConnection()
        session.protocol = protocol
        protocol.makeConnection(session)

    def getHost():
        if self.cspTcpPort:
            return self.cspTcpPort.getHost()
        elif self.resource:
            pass # TODO: how do we do getHost if we just have self.resource?
