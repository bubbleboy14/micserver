from chesstools import Board, Move, List, Timer, TimeLockTimer

timer = {True: TimeLockTimer, False: Timer}

class Game(object):
    def __init__(self, p1, p2, initial, increment, timelock):
        self.white = p1
        self.black = p2
        self.initial = initial
        self.increment = increment
        self.timelock = timelock
        self.white.start_game(self, 'white')
        self.black.start_game(self, 'black')
        self.moves = List()
        self.board = Board()
        self.timer = timer[timelock](initial, increment)

    def send_move(self, player, move, confirmation):
        self.opponent(player).send(move)
        if self.timelock:
            self.timer.move_sent()
        player.send(confirmation)
        if move.attr('gameover'):
            result = self.check()
            if result:
                self.end(player, result)

    def move_received(self):
        if self.timelock:
            self.timer.move_received()

    def end(self, player, reason):
        if reason in ['agreement','stalemate','50-move rule','repetition']:
            outcome = '1/2-1/2'
        elif reason in ['timeout','forfeit']:
            outcome = self.white is player and '0-1' or '1-0'
        elif reason == 'checkmate':
            outcome = self.white is player and '1-0' or '0-1'
        self.moves.outcome = outcome
        if self.moves.last_move:
            self.moves.last_move.comment = reason
        self.white.gameover(outcome, reason)
        self.black.gameover(outcome, reason)

    def timeout(self, player):
        self.timer.update()
        if self.timer.get_opponent(player.color) < 0:
            self.end(self.opponent(player), 'timeout')

    def draw(self, player):
        player.draw_offered = True
        opp = self.opponent(player)
        opp.draw()
        if opp.draw_offered:
            self.end(player, 'agreement')

    def move(self, start, end, promotion=None):
        m = Move(start, end, promotion)
        if self.board.is_legal(m):
            if not self.moves.last_move:
                self.timer.start()
            self.timer.switch()
            w, b = self.timer.get_seconds()
            self.white.timers(w, b)
            self.black.timers(w, b)
            self.moves.add(m)
            self.board.move(m)
            return True
        else:
            return False

    def check(self):
        return self.board.check_position()

    def turn(self):
        return self.board.turn

    def opponent(self, player):
        return self.white is player and self.black or self.white

    def get_fen(self):
        return self.board.fen()

    def get_board(self):
        return self.board.render()

    def get_moves(self):
        return str(self.moves)

    def render(self):
        print self.get_fen() + '\n' + self.get_board() + '\n' + self.get_moves()