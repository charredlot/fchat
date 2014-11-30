from chat import app, init_chat
from gevent import monkey
from socketio.server import SocketIOServer


monkey.patch_all()

LISTEN_IP = '10.240.220.185' 
LISTEN_PORT = 5000

if __name__ == '__main__':
    init_chat()
    print 'Listening on http://%s:%s and on port 10843 (flash policy server)' % (LISTEN_IP, LISTEN_PORT)
    SocketIOServer((LISTEN_IP, LISTEN_PORT), app, resource="socket.io").serve_forever()
