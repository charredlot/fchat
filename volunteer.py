
import os
import string

class VolunteerMgr(object):
    volunteers = None
    available = None
    room_ids = None
    namespaces = None

    def __init__(self):
        self.volunteers = dict()
        self.available = dict()
        self.room_ids = set()
        self.namespaces = dict()
        self.load_from_db()

    def load_from_db(self):
        #self.volunteers = dict( ((email, Volunteer(email, email, calls_max)) for email, calls_max in TMP_DB) )
        pass

    def get_volunteer(self, email):
        try:
            return self.volunteers[email]
        except KeyError:
            vol = Volunteer(email, 1)
            self.volunteers[email] = vol
            return vol

    def set_available(self, vol):
        if vol.username in self.available:
            return
        self.available[vol.username] = vol

    def is_available(self, vol_name):
        return vol_name in self.available

    def num_available(self):
        return len(self.available)

    def hangup(self, room_id):
        try:
            self.room_ids.remove(room_id)
            return True
        except KeyError:
            return False

    def add_namespace(self, vol, namespace):
        self.namespaces[vol.username] = namespace

class Volunteer(object):
    username = None
    email = None
    _is_on_call = False
    _calls_max = 1
    _calls_current = 0
    def __init__(self, username, email, calls_max=1):
        self.username = unicode(username)
        self.email = unicode(email)
        self._is_on_call = False
        self._calls_max = calls_max
        self._calls_current = 0

    def get_calls_max(self):
        return self._calls_max

    def get_calls_current(self):
        return self._calls_current

    def is_available(self):
        return self._is_on_call and (self._calls_current < self._calls_max)

    def add_call(self):
        self._calls_curent += 1
        return self._calls_current

    def remove_call(self):
        self._calls_curent -= 1
        return self._calls_current
