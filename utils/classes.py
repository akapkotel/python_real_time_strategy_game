#!/usr/bin/env python

import heapq

from typing import Callable


class Singleton:
    instances = {}

    def __new__(cls, *args, **kwargs):
        try:
            return Singleton.instances[cls]
        except KeyError:
            Singleton.instances[cls] = singleton = super().__new__(cls)
            return singleton


class HashedList(list):
    """
    Wrapper for a list of currently selected Units. Adds fast look-up by using
    of set containing items id's.
    To work, it requires added items to have an unique 'id' attribute.
    """

    def __init__(self, iterable=None):
        super().__init__()
        self.elements_ids = set()
        if iterable is not None:
            self.extend(iterable)

    def __contains__(self, item) -> bool:
        return item.id in self.elements_ids

    def append(self, item):
        try:
            self.elements_ids.add(item.id)
            super().append(item)
        except AttributeError:
            print("Item must have 'id' attribute which is hashable.")

    def remove(self, item):
        self.elements_ids.discard(item.id)
        try:
            super().remove(item)
        except ValueError:
            pass

    def pop(self, index=-1):
        popped = super().pop(index)
        self.elements_ids.discard(popped.id)
        return popped

    def extend(self, iterable) -> None:
        self.elements_ids.update(i.id for i in iterable)
        super().extend(iterable)

    def insert(self, index, item) -> None:
        self.elements_ids.add(item.id)
        super().insert(index, item)

    def clear(self) -> None:
        self.elements_ids.clear()
        super().clear()

    def where(self, condition: Callable):
        return HashedList([e for e in self if condition(e)])


class PriorityQueue:
    # much faster than sorting list each frame
    def __init__(self, first_element=None, priority=None):
        self.elements = []
        self._contains = set()  # my improvement, faster lookups
        if first_element is not None:
            self.put(first_element, priority)

    def __bool__(self) -> bool:
        return len(self.elements) > 0

    def __len__(self) -> int:
        return len(self.elements)

    def __contains__(self, item) -> bool:
        return item in self._contains

    def not_empty(self) -> bool:
        return len(self.elements) > 0

    def put(self, item, priority):
        self._contains.add(item)
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]  # (priority, item)
