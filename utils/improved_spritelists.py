#!/usr/bin/env python
from __future__ import annotations

from typing import Dict, Optional

from arcade import SpriteList, Sprite

from utils.functions import log


class SpriteListWithSwitch(SpriteList):
    """
    This is a arcade Spritelist improved with parameters: update_on, draw_on
    and method toggle_update() and toggle_draw() which controls if this
    SpriteList is updated and drawn_area each frame or not.
    """

    def __init__(self, use_spatial_hash=False,
                 spatial_hash_cell_size: int = 128,
                 is_static=False,
                 update_on=True,
                 draw_on=True):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)
        self._update_on = update_on
        self._draw_on = draw_on

    @property
    def update_on(self) -> bool:
        return self._update_on

    @property
    def draw_on(self) -> bool:
        return self._draw_on

    def on_update(self, delta_time: float = 1/60):
        if self._update_on:
            super().on_update(delta_time)

    def update(self):
        if self._update_on:
            super().update()

    def draw(self, **kwargs):
        if self._draw_on:
            super().draw(**kwargs)

    def toggle_update(self):
        self._update_on = not self._update_on

    def toggle_draw(self):
        self._draw_on = not self._draw_on


class SelectiveSpriteList(SpriteList):
    """
    This SpriteList works with Sprites having attributes: 'id', 'updated' and
    'rendered'. It is possible to switch updating and drawing of single
    sprites by changing their 'updated' and 'rendered' attributes inside
    their own logic, or by calling 'start_updating', 'start_drawing',
    'stop_updating' and 'stop_drawing' methods of SelectableSpriteList with
    the chosen Sprite as parameter.
    SelectableSpriteList also maintains hashmap of all Sprites which allows for
    fast lookups by their 'id' attribute.
    """

    def __init__(self, use_spatial_hash=False, is_static=False):
        super().__init__(use_spatial_hash, is_static)
        # to keep track of items in spritelist, fast lookups:
        self.registry: Dict[int, Sprite] = {}

    def get_by_id(self, sprite_id: int) -> Optional[Sprite]:
        """Return element with particular 'id' attribute value or None."""
        try:
            return self.registry[sprite_id]
        except KeyError:
            return None

    def __len__(self) -> int:
        return len(self.registry)

    def __contains__(self, sprite) -> bool:
        return sprite.id in self.registry

    def append(self, sprite):
        sprite.selective_spritelist = self
        self.registry[sprite.id] = sprite
        super().append(sprite)

    def remove(self, sprite):
        try:
            del self.registry[sprite.id]
        except KeyError:
            pass
        super().remove(sprite)

    def extend(self, iterable):
        for sprite in iterable:
            self.append(sprite)

    @staticmethod
    def start_updating(sprite):
        try:
            sprite.updated = True
        except AttributeError:
            log(f'Tried to draw Sprite instance without "updated" attribute')

    @staticmethod
    def stop_updating(sprite):
        try:
            sprite.updated = False
        except AttributeError:
            log(f'Tried stop drawing Sprite instance without "updated" attribute')

    @staticmethod
    def start_drawing(sprite):
        try:
            sprite.drawn_area = True
        except AttributeError:
            log(f'Tried to draw Sprite instance without "drawn_area" attribute')

    @staticmethod
    def stop_drawing(sprite):
        try:
            sprite.rendered = False
        except AttributeError:
            log(f'Tried stop drawing Sprite instance without "drawn_area" attribute')

    def on_update(self, delta_time: float = 1/60):
        for sprite in (s for s in self if s.updated):
            sprite.on_update(delta_time)

    def draw(self):
        for sprite in (s for s in self if s.rendered):
            sprite.draw()

    def pop(self, index: int = -1) -> Sprite:
        sprite = super().pop(index)
        del self.registry[sprite.id]
        return sprite

    def clear(self):
        """Safe clearing of the whole SpriteList using reversed order."""
        for _ in range(len(self)):
            self.pop()
