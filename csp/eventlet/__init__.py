import eventlet
from eventlet import wsgi
#from eventlet import api, coros, wsgi
import cgi
import uuid
import base64
try:
    import json
except:
    import simplejson as json
    
    
def test():
    try:
        l = csp_listener(("", 8000))
        while True:
            conn, addr = l.accept()
            print 'ACCEPTED', conn, addr
            eventlet.spawn(echo, conn)
    except KeyboardInterrupt:
        print "Ctr-c, Quitting"
        
def echo(conn):
    conn.send("Welcome")
    while True:
        d = conn.recv(1024)
        print 'RECV', d
        if not d:
            break
        conn.send(d)
        print 'SEND', d
    print "Conn closed"

def csp_listener((interface, port)):
    l = Listener(interface, port)
    l.listen()
    return l

class Listener(object):
    def __init__(self, interface=None, port=None):
        self.interface = interface
        self.port = port
        self._accept_channel = eventlet.queue.Queue(0)
        self._sessions = {}
        
    def listen(self):
        eventlet.spawn(wsgi.server, eventlet.tcp_listener((self.interface, self.port)), self)

    def __call__(self, environ, start_response):
        path = environ['PATH_INFO']
        handler = getattr(self, 'render_' + path[1:], None)
        if not handler:
            start_response('404 Not Found', ())
            return ""
        try:
            form = environ['csp.form'] = get_form(environ)
        except Exception, e:
            raise
            start_response('500 internal server error', [])
            return "Error parsing form"
        session = None
        if path != "/handshake":
            key = form.get("s", None)
            if key not in self._sessions:
                # TODO: error?
                start_response('500 internal server error', [])
                return "'Session not found'"
            session = self._sessions[key]
            session.update_vars(form)
            
        x = handler(session, environ, start_response)
        if not x:
            print "ERROR", path
            return ".."
        return x

    def render_comet(self, session, environ, start_response):
        return session.comet_request(environ, start_response)

    def render_handshake(self, session, environ, start_response):
        key = str(uuid.uuid4()).replace('-', '')
        session = CSPSession(self, key, environ)
        self._sessions[key] = session
        eventlet.spawn(self._accept_channel.put, (session._socket, ("", 0)))
        return session.render_request({"session":key}, start_response)

    def render_close(self, session, environ, start_response):
        session.close()
        return session.render_request("OK", start_response)

    def render_send(self, session, environ, start_response):
        session.read(environ['csp.form'].get('d', ''))
        return session.render_request("OK", start_response)

    def render_reflect(self, session, environ, start_response):
        return environ['csp.form'].get('d', '')
    
    def accept(self):
        return self._accept_channel.get()
    
def get_form(environ):
    form = {}
    qs = environ['QUERY_STRING']
    for key, val in cgi.parse_qs(qs).items():
        form[key] = val[0]
    if environ['REQUEST_METHOD'].upper() == 'POST':
        form['d'] = environ['wsgi.input'].read()
    return form
        
        
class CSPSocket(object):
    def __init__(self, session):
        self.session = session
                
    def send(self, data):
        return self.session.blocking_send(data)
    
    def recv(self, max):
        return self.session.blocking_recv(max)
        
class CSPSession(object):
    
    def __init__(self, parent, key, environ):
        self._recv_event = None
        self.parent = parent
        self.key = key
        self.packets = []
        self.send_id = 0
        self.buffer = ""
        self._read_queue = eventlet.queue.Queue()
        self.is_closed = False
        self.last_received = 0
        self._comet_request_lock = eventlet.semaphore.Semaphore(1)
        self._comet_request_channel = eventlet.queue.Queue(0)
        self.conn_vars = {
            "rp":"",
            "rs":"",
            "du":30,
            "is":0, # False
            "i":0,
            "ps":0,
            "p":"",
            "bp":"",
            "bs":"",
            "g":0, # False
            "se":0, # False
            "ct":"text/html"
        }
        self.prebuffer = ""
        self.update_vars(environ['csp.form'])
        self._socket = CSPSocket(self)
        
    def blocking_send(self, data):
        self.send_id+=1
        self.packets.append([self.send_id, 1, base64.urlsafe_b64encode(data)])
        if self._has_comet_request():
            self._comet_request_channel.put(None)
        return len(data)
    
    def blocking_recv(self, max):
        if not self.buffer:
            self._read_queue.get()
        data = self.buffer[:max]
        self.buffer = self.buffer[max:]
        return data


    def read(self, rawdata):
        # parse packets, throw out duplicates, forward to protocol
        packets = json.loads(rawdata)
        for key, encoding, data in packets:
            data = str(data)
            if self.last_received >= key:
                continue
            if encoding == 1:
                data = base64.urlsafe_b64decode(data + '==' )
            self.last_received = key
            self.buffer += data
            self._read_queue.put(None)

    def update_vars(self, form):
        for key in self.conn_vars:
            if key in form:
                newVal = form[key]
                varType = self.conn_vars[key].__class__
                try:
                    typedVal = varType(newVal)
                    if key == "g" and self._has_comet_request() and self.conn_vars["g"] != typedVal:
                        self.end_stream()
                    self.conn_vars[key] = typedVal
                    if key == "ps":
                        self.prebuffer = " "*typedVal
                except:
                    pass
        ack = form.get("a",["-1"])[0]
        try:
            ack = int(ack)
        except ValueError:
            ack = -1
        while self.packets and ack >= self.packets[0][0]:
            self.packets.pop(0)
        if self.is_closed and not self.packets:
            self.teardown()

    def close(self):
        pass
    
    def _has_comet_request(self):
        return bool(self._comet_request_channel.getting())
    
    def comet_request(self, environ, start_response):
#        print 'self.packets is', self.packets
        if not self.packets:
            self._comet_request_lock.acquire()
            if self._has_comet_request():
                self._comet_request_channel.put(None)
            self._comet_request_lock.release()
#            print 'waiting on something...'
            duration = self.conn_vars['du']
            if duration:
                timer = eventlet.exc_after(duration, Exception("timeout"))
                try:
                    self._comet_request_channel.get()
                    timer.cancel()
                except:
                    # timeout 
                    pass

        headers = [ ('Content-type', self.conn_vars['ct']) ,
                    ('Access-Control-Allow-Origin','*') ]
        start_response("200 Ok", headers)
        
        output = self.render_prebuffer() + self.render_packets(self.packets)
#        print 'returning', output
        return output
            
            
    def render_prebuffer(self):
        return "%s%s"%(self.prebuffer, self.conn_vars["p"])

    def render_packets(self, packets):
        if self.conn_vars['se']:
            sseid = "\r\n"
        else:
            sseid = ""
        if self.conn_vars["se"] and packets:
            sseid = "id: %s\r\n\r\n"%(packets[-1][0],)
        return "%s(%s)%s%s" % (self.conn_vars["bp"], json.dumps(packets), self.conn_vars["bs"], sseid)            

            
#    session.render_request({"session":key}, start_response)
    def render_request(self, data, start_response):
        headers = [ ('Content-type', self.conn_vars['ct']),
                    ('Access-Control-Allow-Origin','*') ]
        start_response("200 Ok", headers)
        output = "%s(%s)%s" % (self.conn_vars["rp"], json.dumps(data), self.conn_vars["rs"])
#        print 'output', output
        return output
    
if __name__ == "__main__": 
    test()
