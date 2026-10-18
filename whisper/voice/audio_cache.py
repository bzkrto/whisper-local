"""Bounded in-memory cache scoped to one loaded TTS voice."""
from collections import OrderedDict
class AudioCache:
    def __init__(self, max_bytes=8*1024*1024):
        self.max_bytes=max_bytes
        self.items=OrderedDict()
        self.bytes=0
    def get(self, key):
        if key not in self.items:return None
        self.items.move_to_end(key)
        return self.items[key]
    def put(self, key, audio):
        if audio.nbytes>self.max_bytes:return
        old=self.items.pop(key,None)
        if old is not None:self.bytes-=old.nbytes
        self.items[key]=audio
        self.bytes+=audio.nbytes
        while self.bytes>self.max_bytes:
            _,value=self.items.popitem(last=False)
            self.bytes-=value.nbytes
