import rel, optparse, datetime
rel.override()
from dez.network import SocketDaemon
from dez.xml_tools import XMLNode
from game import Game

class MICS(object):
    def __init__(self, port, output, timelock, verbose):
        self.output = open(output,'a')
        self.timelock = timelock
        self.verbose = verbose
        self.log("running MICS server on port %s"%port)
        self.server = SocketDaemon('', port, self.__new_conn)
        self.waiting = {}

    def __new_conn(self, conn):
        c = MICSConnection(conn, self.waiting, self.log, self.timelock)

    def log(self, data):
        if self.verbose:
            print data
        self.output.write('[%s] %s\n'%(datetime.datetime.now(), data))
        self.output.flush()

    def start(self):
        self.server.start()

class MICSConnection(object):
    id = 0
    def __init__(self, conn, waiting, log, timelock):
        MICSConnection.id += 1
        self.id = MICSConnection.id
        self.conn = conn
        self.waiting = waiting
        self._log = log
        self.timelock = timelock
        self.reset_vars()
        self.conn.set_close_cb(self.__closed)
        self.conn.set_rmode_xml(self.recv)
        self.active = True
        self.name = None

    def __closed(self):
        self.active = False
        if self.game:
            self.game.end(self, 'forfeit')
        else:
            self.retract_seeks()

    def log(self, data):
        self._log("[conn %s | active = %s]: %s"%(self.id, self.active, data))

    def retract_seeks(self):
        for key, val in self.waiting.copy().items():
            if val is self:
                del self.waiting[key]

    def seek(self, initial=None, increment=None):
        if initial is None: initial = 300
        if increment is None: increment = 0
        g = (initial, increment)
        if g in self.waiting:
            Game(self.waiting[g], self, initial, increment, self.timelock)
        else:
            self.waiting[g] = self

    def reset_vars(self):
        self.game = None
        self.color = None
        self.draw_offered = False

    def recv(self, data):
        self.log("RECV: %s"%data)
        if self.game:
            if data.name == 'move':
                if self.game.turn() == self.color:
                    if self.game.move(data.attr('from'), data.attr('to'), data.attr('promotion')):
                        self.game.send_move(self, data, XMLNode('confirm'))
                    else:
                        self.notice("invalid move")
                else:
                    self.notice("not your move")
            elif data.name == 'received':
                self.game.move_received()
            elif data.name == 'timeout':
                self.game.timeout(self)
            elif data.name == 'chat':
                self.game.opponent(self).chat(self.name, data.children[0])
            elif data.name == 'draw':
                self.game.draw(self)
            elif data.name == 'forfeit':
                self.game.end(self, 'forfeit')
            elif data.name in ['moves','board','fen']:
                x = XMLNode(data.name)
                x.add_child(getattr(self.game, "get_"+data.name)())
                self.send(x)
            else:
                self.notice("unknown command")
        elif data.name == 'seek':
            self.notice("finding game...")
            self.name = data.attr('name')
            self.seek(data.attr('initial'), data.attr('increment'))
        elif data.name == 'list':
            x = XMLNode('list')
            for (initial, increment), player in self.waiting.items():
                s = XMLNode('seek')
                s.add_attribute('initial',initial)
                s.add_attribute('increment',increment)
                s.add_attribute('name',player.name)
                x.add_child(s)
            self.send(x)
        else:
            self.notice("no current game")

    def start_game(self, game, color):
        self.retract_seeks()
        self.game = game
        self.color = color
        x = XMLNode('game')
        x.add_attribute('color', self.color)
        x.add_attribute('initial', game.initial)
        x.add_attribute('increment', game.increment)
        x.add_attribute('white', game.white.name)
        x.add_attribute('black', game.black.name)
        x.add_attribute('timelock', self.timelock and '1' or '0')
        self.send(x)

    def notice(self, data):
        x = XMLNode('notice')
        x.add_child(data)
        self.send(x)

    def gameover(self, outcome, reason):
        x = XMLNode('gameover')
        x.add_attribute('outcome',outcome)
        x.add_attribute('reason',reason)
        self.send(x)
        self.reset_vars()

    def draw(self):
        self.send(XMLNode('draw'))

    def timers(self, w, b):
        x = XMLNode('time')
        x.add_attribute('white',w)
        x.add_attribute('black',b)
        self.send(x)

    def chat(self, name, msg):
        x = XMLNode('chat')
        x.add_attribute('name',name)
        x.add_child(msg)
        self.send(x)

    def send(self, data):
        self.log("SEND: %s"%data)
        if self.active:
            self.conn.write(str(data))

if __name__ == "__main__":
    parser = optparse.OptionParser('server [-p PORT] [-o OUTPUT] [-t] [-v]')
    parser.add_option('-p', '--port', dest='port', default='7777', help='run server on this port. default: 7777')
    parser.add_option('-o', '--output', dest='output', default='output.log', help='set output log')
    parser.add_option('-t', '--timelock', action='store_true', dest='timelock', default=False, help='enable TimeLock timekeeping. compensates for latency, but requires trusted clients.')
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose', default=False, help='turn this on to learn the MICS protocol!')
    ops = parser.parse_args()[0]
    try:
        port = int(ops.port)
    except:
        print "Invalid port: %s"%ops.port
    else:
        server = MICS(port, ops.output, ops.timelock, ops.verbose)
        server.start()