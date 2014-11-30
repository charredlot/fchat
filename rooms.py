
import random
import re
import string
import unicodedata

from socketio.namespace import BaseNamespace

from local_utils import get_rand_string

class ChatRoomMgr(object):
    rooms = None
    room_id = 1
    def __init__(self):
        self.rooms = dict()
        self.room_id = 1

    def _room_name_generate(self):
        name = None
        for i in xrange(100):
            name = get_rand_string(20)
            if not name in self.rooms:
                return name
        return None

    def create_room(self):
        name = self._room_name_generate()
        if not name:
            return None
        
        self.room_id += 1
        room = ChatRoom(name, self.room_id)
        self.rooms[name] = room
        return room

    def get_room(self, name):
        try:
            return self.rooms[name]
        except KeyError:
            return None

class ChatRoom(object):
    name = None
    id = 0
    room_key = None
    volunteer = None
    def __init__(self, name, room_id):
        self.name = name
        self.id = room_id
        self.room_key = get_rand_string(32)
        self.volunteer = None
