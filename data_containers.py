#!/usr/bin/env python
from __future__ import annotations

from typing import Iterable, Optional, Any

from arcade import SpriteList


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

    def where(self, condition):
        return HashedList([e for e in self if condition(e)])


class DividedSpriteList(SpriteList):
    """
    Reasons for this wrapper: (1) speed. Adding additional set allows to
    store ID of each Sprite appended to this SpriteList for faster lookups.
    Hashed set provides lookup in O(1).
    (2) Separating SpriteLists for visible and drawn Sprites and invisible, so
    not drawn. Each Sprite can be stored in drawn, updated or both SpriteLists.
    Not-drawing all Sprites each frame, but only visible saves CPU-time.
    """

    def __init__(self, is_static=False):
        super().__init__(is_static)  # to comply with SpriteList interface
        self.id_elements_dict = {}
        del self.sprite_list  # we replace it with two SpriteLists below:
        self.updated = SpriteList(is_static)
        self.drawn = SpriteList(is_static)
        self.alive_ids = set()

    def __repr__(self) -> str:
        return f'DividedSpriteList, contains: {self.id_elements_dict}'

    def __len__(self) -> int:
        return len(self.alive_ids)

    def __bool__(self) -> bool:
        return len(self.alive_ids) > 0

    def __getitem__(self, item):
        return self.updated[item]

    def __iter__(self) -> Iterable:
        return iter(self.updated)

    def __contains__(self, item) -> bool:
        return item.id in self.alive_ids

    def append(self, item, start_drawing=False):
        if (item_id := item.id) not in self.alive_ids:
            item.divided_spritelist = self
            self.id_elements_dict[item_id] = item
            self.alive_ids.add(item_id)
            self.start_updating(item)
            if start_drawing or item.visible:
                self.start_drawing(item)

    def remove(self, item):
        if (item_id := item.id) in self.alive_ids:
            self.stop_updating(item)
            self.stop_drawing(item)
            self.alive_ids.discard(item_id)
            del self.id_elements_dict[item_id]

    def extend(self, iterable):
        for item in iterable:
            self.append(item)

    def start_updating(self, item):
        self.updated.append(item)

    def stop_updating(self, item):
        try:
            self.updated.remove(item)
        except ValueError:
            pass

    def start_drawing(self, item):
        self.drawn.append(item)

    def stop_drawing(self, item):
        try:
            self.drawn.remove(item)
        except ValueError:
            pass

    def update(self):
        self.updated.update()

    def draw(self):
        self.drawn.draw()

    def pop(self, index: int = -1):
        poped_item = self.updated.pop(index)
        self.remove(poped_item)
        return poped_item

    def select_by_id(self, element_id: int) -> Optional[Any]:
        try:
            return self.id_elements_dict[element_id]
        except KeyError:
            return None
