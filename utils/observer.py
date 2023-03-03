from __future__ import annotations

from abc import abstractmethod
from collections import defaultdict
from typing import Optional, List, DefaultDict, Any


class Observed:
    """
    My implementation of Observer pattern which allows to notify observers when
    any attribute of the subject is changed. Observed object keeps track of
    which Observer is interested in changes of which particular attribute, and
    notifies it only when this attribute changes. It is also possible to attach
    an 'general' Observer, which is notified only, when subject is deleted.
    How the 'deletion' is interpreted is up to the user - it could be when
    __del__ method is called, or when Observed is removed from some collection.
    """

    def __init__(self, observers: Optional[List[Observer]] = None):
        self.observed_attributes: DefaultDict[str, List[Observer]] = defaultdict(list)
        if observers:
            self.attach_observers(observers=observers)

    def __setattr__(self, key, value):
        try:
            if key in self.observed_attributes:
                self.notify_all_observers(key, value)
        except AttributeError:
            pass  # happens only once, during __init__ when observed_attributes is not initialized yet
        finally:
            super().__setattr__(key, value)

    def notify_all_observers(self, key: str, value: Any):
        for observer in self.observed_attributes[key]:
            observer.notify(key, value)

    def attach_observers(self, observers: List[Observer], *attributes: str):
        for observer in observers:
            self.attach(observer, *attributes)

    def attach(self, observer: Observer, *attributes: str):
        if attributes:
            for attribute in attributes:
                self.observed_attributes[attribute].append(observer)
        else:
            self.observed_attributes['on_kill'].append(observer)
        observer.on_being_attached(attached=self)

    def detach_observers(self):
        all_observers = set()
        for observers in self.observed_attributes.values():
            all_observers.update(observers)
        for observer in all_observers:
            self.detach(observer)

    def detach(self, observer: Observer):
        for attribute, observers in self.observed_attributes.items():
            if observer in observers:
                observer.on_being_detached(detached=self)
                observers.remove(observer)


class Observer:

    @abstractmethod
    def on_being_attached(self, attached: Observed):
        raise NotImplementedError

    @abstractmethod
    def notify(self, attribute: str, value: Any):
        raise NotImplementedError

    @abstractmethod
    def on_being_detached(self, detached: Observed):
        raise NotImplementedError
