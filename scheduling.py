#!/usr/bin/env python
from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional, Callable

from utils.functions import log


@dataclass
class ScheduledEvent:
    creator: Any
    delay: int
    function: Callable
    args: Optional[Tuple] = field(default_factory=tuple)
    kwargs: Optional[Dict] = field(default_factory=dict)
    repeat: int = 0
    infinite: bool = False
    frames_left: Optional[int] = None

    def __repr__(self):
        return (f'Event scheduled by: {self.creator.__class__.__name__}, '
                f'function: {self.function.__name__}, args: {self.args}, '
                f'kwargs: {self.kwargs}, frames left: {self.frames_left}')

    def execute(self):
        self.function(*self.args, **self.kwargs)


class EventsScheduler:
    """
    EventScheduler keeps track of scheduled events and counts down frames
    checking each time if there are any events which should be executed. It
    replaces arcade schedule function allowing to serialize and save scheduled
    events, which arcade does not offer.
    """
    instance = None

    def __init__(self, update_rate: float):
        self.update_rate = update_rate
        self.scheduled_events: List[ScheduledEvent] = []
        self.frames_left: List[int] = []
        EventsScheduler.instance = self

    def schedule(self, event: ScheduledEvent):
        log(f'Scheduled event: {event}')
        self.scheduled_events.append(event)
        frames_left = event.frames_left or int(event.delay / self.update_rate)
        self.frames_left.append(frames_left)

    def unschedule(self, event: ScheduledEvent):
        log(f'Unscheduled event: {event}')
        try:
            index = self.scheduled_events.index(event)
            self.scheduled_events.pop(index)
            self.frames_left.pop(index)
        except ValueError:
            pass

    def update(self):
        self.decrease_frames_left()
        self.execute_events()

    def decrease_frames_left(self):
        self.frames_left = list(np.array(self.frames_left) - 1)

    def execute_events(self):
        for i, event in enumerate(self.scheduled_events):
            if not self.frames_left[i]:
                event.execute()
                self.unschedule(event)
                log(f'Executed event: {event}')
                if event.repeat:
                    self.schedule(event)
                    if not event.infinite:
                        event.repeat -= 1

    def frames_left_to_event_execution(self, event: ScheduledEvent) -> int:
        index = self.scheduled_events.index(event)
        return self.frames_left[index]


class EventsCreator:
    """
    Inherit from this class in each object you want to be able to schedule
    ScheduledEvents. It keeps track of all events created by the object making
    it possible to shelve them when application state is saved to shelve file.
    """
    event_scheduler: Optional[EventsScheduler] = None

    def __init__(self):
        self.scheduled_events: List[ScheduledEvent] = []

    def schedule_event(self, event: ScheduledEvent):
        self.add_event_to_scheduled_list(event)
        EventsScheduler.instance.schedule(event)

    def unschedule_event(self, event: ScheduledEvent):
        self.remove_event_from_scheduled_list(event)
        EventsScheduler.instance.unschedule(event)

    def add_event_to_scheduled_list(self, event: ScheduledEvent):
        self.scheduled_events.append(event)

    def remove_event_from_scheduled_list(self, event: ScheduledEvent):
        self.scheduled_events.remove(event)

    def scheduled_events_to_shelve_data(self) -> List[Dict]:
        """
        Call it in __getstate__ method to save self.scheduled_events of an
         object.
         """
        scheduler = EventsScheduler.instance
        return [
            {'frames_left': scheduler.frames_left_to_event_execution(event),
             'delay': event.delay,
             'function_name': event.function.__name__,
             'self': 'self' if hasattr(event.function, '__self__') else None,
             'args': event.args,
             'kwargs': event.kwargs,
             'repeat': event.repeat,
             'infinite': event.infinite} for event in self.scheduled_events
        ]

    def shelve_data_to_scheduled_events(self, shelve_data: List[Dict]) -> List[ScheduledEvent]:
        # call it in __setstate__ method
        return [
            ScheduledEvent(
                creator=self,
                delay=data['delay'],
                function=eval(f"{data['self']}.{data['function_name']}" if
                              data['self'] else data['function_name']),
                args=data['args'],
                kwargs=data['kwargs'],
                repeat=data['repeat'],
                infinite=data['infinite'],
                frames_left=data['frames_left']
            )
            for data in shelve_data
        ]

    @staticmethod
    def get_function_bound_object(function: Callable) -> Optional[str]:
        if hasattr(function, '__self__'):
            return 'self'

    def scheduling_test(self):
        """
        Function created for testing purposes only. You can schedule it
        from any object inheriting the EventsCreator interface to test if
        scheduling works properly:

        event = ScheduledEvent(self, 2, self.scheduling_test, repeat=True)
        self.schedule_event(event)
        """
        log(f'Hi, this is an event created by: {self}', console=True)
