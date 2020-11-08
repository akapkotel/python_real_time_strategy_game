#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod
from typing import Set


class OwnedObject:
    """
    My implementation of Observer Pattern which main reason is to provide an
    abstract interface for game objects to work with owner-subject relations.
    Each ObjectsOwner can 'possess' (observe) many OwnedObjects. OwnedObject is
    responsible for registering itself in the proper ObjectsOwners, and they
    are responsible for handling the registering implementation.
    """

    def __init__(self, owners=False):
        """-
        :param owners: bool : default: False. Change it to True if you want
        this OwnedObjects to use default Set[ObjectsOwner] to keep track of
        the objects owning this instance. If implementing your own collection,
        leave it False.
        """
        self._owners: Set[ObjectsOwner] = set() if owners else None
        self._state = None

    def register_to_objectsowners(self, *owners: ObjectsOwner):
        if self._owners is not None:
            self._owners.update(owners)
        for owner in owners:
            owner.register(self)

    def unregister_from_objectsowner(self, owner: ObjectsOwner):
        if self._owners is not None:
            self._owners.discard(owner)
        owner.unregister(self)

    def notify_owners(self, *args, **kwargs):
        for owner in self._owners:
            owner.get_notified(*args, **kwargs)

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, arg):
        self._state = arg
        self.notify_owners()

    def unregister_from_all_owners(self):
        """Remember to call this method in objects __kill__."""
        if self._owners is not None:
            for owner in self._owners.copy():
                owner.unregister(self)
            self._owners.clear()


class ObjectsOwner:
    """
    ObjectsOwner has only a bunch of abstract methods used to add new
    OwnedObjects and remove them. These methods must be implemented for each
    subclass individually, since each type of ObjectsOwner will handle
    different types of OwnedObjects for various reasons and use them for it's
    own purposes.
    CLasses inheriting from ObjectsOwner must keep their own containers for
    their registered OwnedObjects, since this class does not provide default
    one. Reason for that is to force subclasses to name their data-attributes
    properly to their usage and type of OwnedObjects stored inside.
    """

    @abstractmethod
    def register(self, acquired: OwnedObject):
        raise NotImplementedError

    @abstractmethod
    def unregister(self, owned: OwnedObject):
        raise NotImplementedError

    @abstractmethod
    def get_notified(self, *args, **kwargs):
        raise NotImplementedError
