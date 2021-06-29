#!/usr/bin/env python
from __future__ import annotations
from math import inf
from typing import List, Tuple, Dict, Any, Optional, Callable, Union

from utils.logging import log, logger


class ScheduledEvent:
    """
    This event is an alternative to the pyglet.clock.schedule. ScheduledEvent
    can be pickled with shelve module and does not require scheduled functions
    to have additional float parameter for schedule delay, so it's signature is
    not touched.
    """

    def __init__(self, creator: Any, delay: float, function: Callable,
                 args: Optional[Tuple] = None, kwargs: Optional[Dict] = None,
                 repeat: int = 0, delay_left: Optional[float] = None):
        """
        :param creator: python object, which created this event
        :param delay: float -- seconds to wait for event to be executed
        :param function: bound method o functions
        :param args: tuple -- positional arguments for scheduled functions
        :param kwargs: dict -- named arguments for scheduled functions
        :param repeat: int -- how many times this event should be executed,
        set it to -1 to create event scheduled in infinite loop
        :param delay_left: float -- for internal use, ignore it
        """
        self.creator = creator
        self.delay = delay
        self.function = function
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.repeat = inf if repeat == -1 else repeat
        self.delay_left = delay_left

    def __repr__(self):
        return (f'Event scheduled by: {self.creator.__class__.__name__}, '
                f'function: {self.function.__name__}, args: {self.args}, '
                f'kwargs: {self.kwargs}, time left: {self.delay_left}')

    @logger()
    def execute(self):
        try:
            self.function(*self.args, **self.kwargs)
        except Exception as e:
            log(f'{self} failed to execute with exception: {str(e)}')

    def shelve(self):
        return {
            'creator': self.get_creator_name(),
            'delay': self.delay,
            'function': self.function.__name__,
            'args': self.args,
            'kwargs': self.kwargs,
            'repeat': self.repeat,
            'delay left': EventsScheduler.instance.time_left_to_event_execution(self)
        }

    def get_creator_name(self) -> Union[str, Tuple[str, int]]:
        try:
            identifier = self.creator.id
            return self.creator.__class__.__name__, identifier
        except AttributeError:
            return self.creator.__class__.__name__

    def unshelve(self):
        raise NotImplementedError


class EventsScheduler:
    """
    EventScheduler keeps track of scheduled events and counts down frames
    checking each time if there are any events which should be executed. It
    replaces arcade schedule functions allowing to serialize and save scheduled
    events, which arcade does not offer.
    """
    instance = None

    def __init__(self, game):
        self.game = game
        self.schedulers: List[EventsCreator] = []
        self.scheduled_events: List[ScheduledEvent] = []
        self.execution_times: List[float] = []
        EventsScheduler.instance = self

    @logger()
    def schedule(self, event: ScheduledEvent):
        self.schedulers.append(event.creator)
        self.scheduled_events.append(event)
        delay = event.delay_left or event.delay
        self.execution_times.append(self.game.timer['total'] + delay)

    @logger()
    def unschedule(self, index: int):
        try:
            self.schedulers.pop(index)
            self.scheduled_events.pop(index)
            self.execution_times.pop(index)
        except ValueError:
            pass

    def update(self):
        time = self.game.timer['total']
        for i, event in enumerate(self.scheduled_events):
            if time >= self.execution_times[i]:
                event.execute()
                self.unschedule(i)
                if event.repeat:
                    event.repeat -= 1
                    self.schedule(event)

    def time_left_to_event_execution(self, event: ScheduledEvent) -> float:
        index = self.scheduled_events.index(event)
        return self.game.timer['total'] - self.execution_times[index]

    def save(self) -> List[Dict]:
        return self.shelve_scheduled_events()

    def shelve_scheduled_events(self) -> List[Dict]:
        return [event.shelve() for event in self.scheduled_events]

    def load(self, shelved_events: List[Dict]):
        self.unshelve_scheduled_events(shelved_events)

    def unshelve_scheduled_events(self, shelved_events: List[Dict]):
        for shelved in shelved_events:
            print(shelved)
            creator = self.game.find_object_by_class_and_id(shelved['creator'])
            delay = shelved['delay']
            function = getattr(creator, shelved['function'])
            self.schedule(
                ScheduledEvent(creator, delay, function, *list(shelved.values())[3:])
            )


class EventsCreator:
    """
    Inherit from this class in each object you want to be able to schedule
    ScheduledEvents. It keeps track of all events created by the object making
    it possible to shelve them when application state is saved to shelve file.
    """

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
        log(f'Hi, event created by: {self} was executed properly', console=True)
