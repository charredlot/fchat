import json
import random
import re
import requests
import string
import unicodedata
import urllib

import socketio
from socketio import socketio_manage
from socketio.namespace import BaseNamespace
from socketio.mixins import RoomsMixin, BroadcastMixin
from werkzeug.exceptions import NotFound
from gevent import monkey

from flask import Flask, Response, request, render_template, url_for, redirect, make_response
from flask.ext.login import session, current_user, LoginManager

from local_utils import slugify, get_rand_string
from rooms import ChatRoomMgr, ChatRoom
from volunteer import Volunteer, VolunteerMgr
from settings import Settings

monkey.patch_all()

JS_VERSION_HACK=21

URL_CONNECT_PREFIX = 'connect'
URL_ROOM_PREFIX = 'room'
URL_ON_CALL_PREFIX = 'on_call'
LOGIN_CALLBACK_URL='/login_callback'

app = Flask(__name__)
app.secret_key = 'ameklfmaekvdfklvnow4' # so don't have to relog for testing, should be get_rand_string(32)
app.debug = True

# no persistent for now
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/chat.db'
#db = SQLAlchemy(app)

volunteer_mgr = None
room_mgr = None

# utils
def get_volunteer_from_session(session):
    try:
        email = session['email']
        return volunteer_mgr.get_volunteer(email)
    except KeyError:
        return None

def is_volunteer_session(session):
    return 'email' in session

def build_url_on_call(email):
    return '/{0}/{1}'.format(URL_ON_CALL_PREFIX, slugify(email))

def build_url_room(room):
    return '/{0}/{1}'.format(URL_ROOM_PREFIX, room.name)

def alert_volunteers(room):
    for email, namespace in volunteer_mgr.namespaces.iteritems():
        namespace.broadcast_event('new_call', room.id, build_url_room(room))

# views
@app.route('/{0}/<name>'.format(URL_ROOM_PREFIX))
def room(name):
    room = room_mgr.get_room(name)
    if not room:
        raise NotFound()

    vol = get_volunteer_from_session(session)
    if vol:
        if not room.volunteer is None:
            return render_template(url_for('already_answered'))
        
        room.volunteer = vol     
    else:
        try:
            # TODO: oh noes break early string cmp
            if session['room_key'] != room.room_key:
                raise NotFound()
        except KeyError:
            raise NotFound()

    return render_template('room.html', room=room, js_version_hack=JS_VERSION_HACK)

@app.route('/already_answered')
def already_answered():
    return "Sorry that call was already answered"

@app.route('/call')
def call():
    # TODO: verify user doesn't have a bunch of rooms (based on ip and cookie)
    room = room_mgr.create_room()
    if not room:
        # TODO: explanatory error
        return redirect(url_for('index'))
    else:
        session['room_key'] = room.room_key
        alert_volunteers(room)
        return redirect(url_for('room', name=room.name))

@app.route('/{0}/<email>'.format(URL_ON_CALL_PREFIX))
def on_call(email):
    vol = get_volunteer_from_session(session)
    if not vol:
        return 'Please <a href="/login">login</a>'

    # TODO: store per-volunteer room?
    room = room_mgr.create_room()
    if not room:
        # TODO: explanatory error
        return redirect(url_for('index'))
    else:    
        return render_template('on_call.html', room=room, js_version_hack=JS_VERSION_HACK)

@app.route('/dashboard')
def dashboard():
    vol = get_volunteer_from_session(session)
    if not vol:
        return 'Please <a href="/login">login</a>'
    return render_template('dashboard.html',
              on_call_url = build_url_on_call(vol.email),
              current_calls=vol.get_calls_current(),
              max_calls=vol.get_calls_max())

@app.route('/login')
def login():
    params = dict(
        response_type   = 'code',
        scope           = Settings.GAUTH_SCOPE,
        client_id       = Settings.GAUTH_CLIENT_ID,
        approval_prompt = 'force',
        redirect_uri     = '{0}{1}'.format(Settings.EXTERNAL_ADDRESS, LOGIN_CALLBACK_URL))
    url = Settings.GAUTH_URI + '?' + urllib.urlencode(params)
    return redirect(url)

@app.route(LOGIN_CALLBACK_URL)
def login_callback():
    if 'code' in request.args:
        code = request.args.get('code')
        data = dict(code=code,
                    client_id=Settings.GAUTH_CLIENT_ID,
                    client_secret=Settings.GAUTH_SECRET,
                    redirect_uri     = '{0}{1}'.format(Settings.EXTERNAL_ADDRESS, LOGIN_CALLBACK_URL),
                    grant_type='authorization_code')

        r = requests.post(Settings.GAUTH_TOKEN_URI, data=data)
        access_token = r.json()['access_token']

        r = requests.get(Settings.GAUTH_PROFILE_URI, params={'access_token': access_token})

        client_email = r.json()['email']

        vol = volunteer_mgr.get_volunteer(client_email)
        if not vol:
            return redirect(url_for('unknown_volunteer'))

        session['access_token'] = access_token
        session['email'] = client_email 
        return redirect(url_for('dashboard'))
    else:
        return 'ERROR'

@app.route('/unknown_volunteer')
def unknown_volunteer():
    return 'TODO TODO email not in database, sorry'

@app.route('/logout')
def logout():
    """Revoke current user's token and reset their session."""
    try:
        del session['email']
    except KeyError:
        pass

    try:
        access_token = session['access_token']
        del session['access_token']
    except KeyError:
        access_token = None

    if access_token:
        r = requests.get(Settings.GAUTH_TOKEN_REVOKE_URI, params={'token': access_token})
    session.clear()

    return redirect(url_for('index')) 

@app.route('/socket.io/<path:remaining>')
def socketio_handler(remaining):
    namespaces = { '/chat' : ChatNamespace }

    vol = get_volunteer_from_session(session)
    if vol:
        namespaces['/event'] = EventNamespace
 
    try:
        # request param is opaque object stored in the namespace.request
        socketio_manage(request.environ,
                        namespaces,
                        request=vol)
    except:
        app.logger.error("Exception while handling socketio connection",
                         exc_info=True)

    return Response()

@app.route('/')
def index():
    if is_volunteer_session(session):
        return redirect(url_for('dashboard'))

    return render_template('index.html',
                num_avail_volunteers=volunteer_mgr.num_available())

def volunteers():
    return render_template('volunteers.html',
                link_prefix = URL_CONNECT_PREFIX,
                volunteers = volunteer_mgr.volunteers)

class EventNamespace(BaseNamespace, BroadcastMixin):
    def initialize(self, *args, **kwargs):
        super(EventNamespace, self).initialize(*args, **kwargs)
        self.logger = app.logger

        vol = self.request
        if vol:
            volunteer_mgr.add_namespace(vol, self)
    
    def on_register(self, msg):
        pass

class ChatNamespace(BaseNamespace, RoomsMixin, BroadcastMixin):
    nicknames = []

    def initialize(self):
        self.logger = app.logger
        self.log("Socketio chatnamespace started")

    def log(self, message):
        self.logger.info("[{0}] {1}".format(self.socket.sessid, message))

    def on_join(self, room):
        self.room = room
        self.join(room)
        self.emit_to_room(self.room, 'nicknames', self.nicknames)
        return True

    def on_nickname(self, nickname):
        self.log('Nickname: {0}'.format(nickname))
        self.nicknames.append(nickname)
        self.session['nickname'] = nickname
        #self.broadcast_event('announcement', '%s has connected' % nickname)
        self.broadcast_event('nicknames', self.nicknames)
        self.emit_to_room(self.room, 'nicknames', self.nicknames)
        self.emit_to_room(self.room, 'msg_to_room', nickname, '{0} has connected'.format(nickname))
        return True, nickname

    def recv_disconnect(self):
        # Remove nickname from the list.
        self.log('Disconnected')

        try:
            nickname = self.session['nickname']
            self.nicknames.remove(nickname)
        except KeyError:
            self.disconnect(silent=True)
            return True

        #self.broadcast_event('announcement', '%s has disconnected' % nickname)
        #self.broadcast_event('nicknames', self.nicknames)
        self.emit_to_room(self.room, 'nicknames', self.nicknames)
        self.emit_to_room(self.room, 'msg_to_room', nickname, '{0} has disconnected'.format(nickname))

        self.disconnect(silent=True)
        return True

    def on_user_message(self, msg):
        #self.log('User message: {0}'.format(msg))
        self.emit_to_room(self.room, 'msg_to_room',
            self.session['nickname'], msg)
        return True

def init_volunteers():
    global volunteer_mgr
    volunteer_mgr = VolunteerMgr()

def init_chat():
    global room_mgr
    room_mgr = ChatRoomMgr()
    init_volunteers()
    login_manager = LoginManager()
    login_manager.setup_app(app)

if __name__ == '__main__':
    init_chat()
    app.run()
