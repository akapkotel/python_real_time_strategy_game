#!/usr/bin/env python
from __future__ import annotations

from typing import Set
from abc import abstractmethod


class OwnedObject:

    def __init__(self):
        self._owners: Set[ObjectsOwner] = set()
        self._state = None

    def register(self, *owners: ObjectsOwner):
        for owner in owners:
            self._owners.add(owner)
            owner.register(self)

    def unregister(self, owner: ObjectsOwner):
        self._owners.discard(owner)
        owner.unregister(self)

    def notify_owners(self, *args, **kwargs):
        for owner in self._owners:
            owner.notify(*args, **kwargs)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, arg):
        self._state = arg
        self.notify_owners()

    def unregister_from_all_owners(self):
        """Remember to call this method in objects __kill__."""
        for owner in self._owners:
            self.unregister(owner)


class ObjectsOwner:
    """
    ObjectsOwner has only a bunch of abstract methods used to add new
    OwnedObjects and remove them. These methods must be implemented for each
    subclass individually.
    """

    @abstractmethod
    def register(self, acquired: OwnedObject):
        raise NotImplementedError

    @abstractmethod
    def unregister(self, owned: OwnedObject):
        raise NotImplementedError

    @abstractmethod
    def notify(self, *args, **kwargs):
        raise NotImplementedError
