#!/usr/bin/env python

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

    def pop(self, index=None):
        popped = super().pop(index)
        self.elements_ids.discard(popped.id)
        return popped

    def extend(self, iterable) -> None:
        for i in iterable:
            self.elements_ids.add(i.id)
        super().extend(iterable)

    def insert(self, index, item) -> None:
        self.elements_ids.add(item.id)
        super().insert(index, item)

    def clear(self) -> None:
        self.elements_ids.clear()
        super().clear()

    def where(self, condition: Callable):
        return HashedList([e for e in self if condition(e)])


class QuadTree:

    def __init__(self, min_x, min_y, max_x, max_y):
        self.min_x = min_x
        self.min_y = min_y
        self.max_x = max_x
        self.max_y = max_y





