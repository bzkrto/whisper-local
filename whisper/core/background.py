"""Cooperative background inference; foreground gets the same model lock next."""
from contextlib import contextmanager


class AnyEvent:
    def __init__(self,*events):self.events=events
    def is_set(self):return any(event.is_set() for event in self.events)


@contextmanager
def background_inference(brain,phase,stop):
    cancelled=AnyEvent(stop,brain._foreground_waiting)
    brain._background_phase=phase
    model=brain.llm
    supports=getattr(type(model),'supports_background_cancel',False)
    previous=getattr(model,'_background_cancel',None) if supports else None
    if supports:model._background_cancel=cancelled
    try:yield cancelled if supports else stop
    finally:
        if supports:model._background_cancel=previous
        brain._background_phase=''
